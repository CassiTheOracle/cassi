#!/usr/bin/env python3
"""Independent verifier for the field-owned architecture redesign campaign.

This verifier intentionally does not import ``redesign_lab``.  It rebuilds the
bounded question catalog and Architecture IR as independent data, reads the
persisted field through its public semantic surface plus authenticated
checkpoint closure, and exercises replay/restart/reopen and mutation controls.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

RECEIPT_SCHEMA = "cassimindfield.redesign-receipt.v1"
FIELD_QUESTION_SCHEMA = "cassimindfield.field-question.v2"
FIELD_SELECTION_SCHEMA = "cassimindfield.field-selection.v3"
MIGRATION_SCHEMA = "cassimindfield.field-state-migration.v1"
STATE_SCHEMA = "cassimindfield.redesign-state.v1"
MAX_VARIANTS = 4
FAMILY_ORDER = ("api-successor-v1", "module-boundary-v1", "facade-adapter-v1")
FAMILIES = set(FAMILY_ORDER)
INVESTIGATION_PROCEDURE_ID = "redesign-procedure:topology-construction"
CROSS_WORLD_SCHEMA = "cassimindfield.cross-world-transfer.v1"
CONSTRAINT_WORLD_SCHEMA = "cassimindfield.constraint-world-transfer.v1"
REASONING_WORLD_SCHEMA = "cassimindfield.paired-reasoning-transfer.v1"
FIELD_PROGRAM_SCHEMA = "cassifi.structured-field-program.v1"
ROOT = Path(__file__).resolve().parent
MIND_FIELD = ROOT.parent / "CassiMindField"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def workspace_digest(files: Mapping[str, str]) -> str:
    return digest({path: hashlib.sha256(files[path].encode("utf-8")).hexdigest() for path in sorted(files)})


def independent_field_program_task(
    files: Mapping[str, str],
    parent_digest: str,
) -> dict[str, Any]:
    function_count = 0
    dependency_edges = 0
    for path, source in sorted(files.items()):
        tree = ast.parse(source, filename=path)
        function_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        dependency_edges += sum(
            len(node.names) if isinstance(node, (ast.Import, ast.ImportFrom)) else 0
            for node in ast.walk(tree)
        )
    file_count = len(files)
    base = (file_count * 7 + function_count * 3) % 128
    delta = max(1, dependency_edges % 17)
    repetitions = max(2, min(8, file_count))
    expected = (base + delta * repetitions) % 256
    body = {
        "schema": "cassimindfield.cross-world-task.v1",
        "source_world": "python-architecture",
        "target_world": "cassifi-structured-field-program",
        "parent_source_digest": parent_digest,
        "topology": {
            "dependency_edges": dependency_edges,
            "file_count": file_count,
            "function_count": function_count,
        },
        "construction_ir": {
            "base": base,
            "delta": delta,
            "repetitions": repetitions,
            "emit_stack": "left",
        },
        "causal_prediction": {
            "accumulator": expected,
            "left": [expected],
            "right": [],
            "status": "halted",
        },
    }
    return {**body, "task_sha256": digest(body)}


def independent_structured_source(task: Mapping[str, Any]) -> dict[str, Any]:
    construction = task["construction_ir"]
    return {
        "schema": FIELD_PROGRAM_SCHEMA,
        "constants": {
            "BASE": int(construction["base"]),
            "DELTA": int(construction["delta"]),
        },
        "functions": {
            "advance": [{"op": "add_acc", "value": "DELTA"}],
        },
        "main": [
            {"op": "set_acc", "value": "BASE"},
            {
                "op": "repeat",
                "count": int(construction["repetitions"]),
                "body": [{"op": "call", "function": "advance"}],
            },
            {"op": "push_acc", "stack": str(construction["emit_stack"])},
        ],
    }


def independent_execute_field_program(source: Mapping[str, Any]) -> dict[str, Any]:
    from cassi_field_computer import ComputerProfile, FieldComputer
    from cassi_field_program import compile_structured_program

    compiled = compile_structured_program(source)
    machine = FieldComputer(
        ComputerProfile(
            program_capacity=len(compiled.program) + 2,
            stack_capacity=16,
            max_steps=max(64, len(compiled.program) * 4),
        )
    )
    state, receipt = machine.run(
        machine.initial(
            compiled.program,
            left=compiled.left,
            right=compiled.right,
        )
    )
    inspected = machine.inspect(state)
    return {
        "compiled_instruction_count": len(compiled.program),
        "compiled_source_sha256": compiled.source_sha256,
        "execution": {
            "accumulator": inspected["accumulator"],
            "left": inspected["left"],
            "right": inspected["right"],
            "status": inspected["status"],
        },
        "logical_steps": receipt["transitions_executed"],
    }


def independent_constraint_task(
    files: Mapping[str, str],
    parent_digest: str,
) -> dict[str, Any]:
    function_count = 0
    dependency_edges = 0
    for path, source in sorted(files.items()):
        tree = ast.parse(source, filename=path)
        function_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        dependency_edges += sum(
            len(node.names)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            else 0
            for node in ast.walk(tree)
        )
    topology = {
        "dependency_edges": dependency_edges,
        "file_count": len(files),
        "function_count": function_count,
    }
    horizon = 3 + topology["file_count"] % 2
    initial = {
        "phase": topology["function_count"] % 2,
        "carry": topology["dependency_edges"] % 2,
    }
    planted_inputs = [
        int(parent_digest[index], 16) % 2 for index in range(horizon)
    ]
    phase = initial["phase"]
    carry = initial["carry"]
    for drive in planted_inputs:
        phase, carry = phase ^ drive, phase if drive else carry
    body = {
        "schema": "cassimindfield.constraint-world-task.v1",
        "source_world": "python-architecture",
        "target_world": "cassifi-boolean-transition-constraint",
        "parent_source_digest": parent_digest,
        "topology": topology,
        "construction_ir": {
            "state": ["phase", "carry"],
            "inputs": ["drive"],
            "horizon": horizon,
            "initial": initial,
            "input_prefix": planted_inputs[:-1],
            "planted_input_trace": planted_inputs,
            "final": {"phase": phase, "carry": carry},
        },
        "causal_prediction": {
            "status": "sat",
            "final": {"phase": phase, "carry": carry},
            "witness_required": True,
        },
    }
    return {**body, "task_sha256": digest(body)}


def independent_constraint_source(task: Mapping[str, Any]) -> dict[str, Any]:
    construction = task["construction_ir"]
    initial = construction["initial"]
    final = construction["final"]
    return {
        "kind": "transition",
        "state": ["phase", "carry"],
        "inputs": ["drive"],
        "gates": [
            {
                "op": "xor",
                "out": "next_phase",
                "args": ["phase", "drive"],
            },
            {
                "op": "mux",
                "out": "next_carry",
                "args": ["drive", "phase", "carry"],
            },
        ],
        "next_state": [
            ["phase", "next_phase"],
            ["carry", "next_carry"],
        ],
        "horizon": int(construction["horizon"]),
        "initial": [
            ["phase", int(initial["phase"])],
            ["carry", int(initial["carry"])],
        ],
        "input_assertions": [
            [time, "drive", int(value)]
            for time, value in enumerate(construction["input_prefix"])
        ],
        "final": [
            ["phase", int(final["phase"])],
            ["carry", int(final["carry"])],
        ],
        "relations": [],
        "clauses": [],
    }


def independent_constraint_audit(
    source: Mapping[str, Any],
    witness: Mapping[str, Any],
) -> dict[str, Any]:
    initial = {str(name): int(value) for name, value in source["initial"]}
    phase = initial["phase"]
    carry = initial["carry"]
    trajectory = [{"time": 0, "phase": phase, "carry": carry}]
    drives = []
    for time in range(int(source["horizon"])):
        key = f"drive@{time}"
        require(key in witness, f"constraint witness omitted {key}")
        drive = int(witness[key])
        require(drive in (0, 1), "constraint witness is not Boolean")
        drives.append(drive)
        phase, carry = phase ^ drive, phase if drive else carry
        trajectory.append(
            {"time": time + 1, "phase": phase, "carry": carry}
        )
    for time, name, expected in source["input_assertions"]:
        require(
            name == "drive" and drives[int(time)] == int(expected),
            "constraint witness violated a pinned input",
        )
    final = {str(name): int(value) for name, value in source["final"]}
    require(
        {"phase": phase, "carry": carry} == final,
        "constraint witness violated the final boundary",
    )
    return {
        "input_trace": drives,
        "trajectory": trajectory,
        "final": {"phase": phase, "carry": carry},
        "status": "PASS",
    }


def independent_constraint_models(
    source: Mapping[str, Any],
) -> list[list[int]]:
    horizon = int(source["horizon"])
    valid: list[list[int]] = []
    for integer in range(1 << horizon):
        trace = [(integer >> time) & 1 for time in range(horizon)]
        witness = {
            f"drive@{time}": value for time, value in enumerate(trace)
        }
        try:
            independent_constraint_audit(source, witness)
        except AssertionError:
            continue
        valid.append(trace)
    return valid


def independent_execute_constraint(source: Mapping[str, Any]) -> dict[str, Any]:
    from cassi_constraint_field import (
        ConstraintField,
        ConstraintFieldProfile,
        compile_transition_problem,
    )

    compiled = compile_transition_problem(source)
    profile = ConstraintFieldProfile(
        max_variables=compiled.variables,
        max_clauses=len(compiled.clauses) + 64,
        max_transitions=20_000,
        max_learned_clauses=64,
        mode="conflict",
        controller=False,
        controller_size=8,
    )
    field = ConstraintField(profile)
    state = field.initial(compiled)
    transitions = 0
    while field.status(state) == "running":
        state, _ = field.step(state)
        transitions += 1
        require(
            transitions <= profile.max_transitions,
            "constraint solver exceeded the declared transition bound",
        )
    result = field.result(state)
    require(result["status"] == "sat", "constraint field did not return SAT")
    witness = result["witness"]
    require(isinstance(witness, Mapping), "SAT result has no witness")
    audit = independent_constraint_audit(source, witness)
    return {
        "compiled_problem_sha256": compiled.sha256,
        "compiled_variables": compiled.variables,
        "compiled_clauses": len(compiled.clauses),
        "status": result["status"],
        "reason": result["reason"],
        "witness": dict(sorted(witness.items())),
        "witness_audit": audit,
        "field_transitions": transitions,
    }


def independent_paired_reasoning_task(
    files: Mapping[str, str],
    parent_digest: str,
) -> dict[str, Any]:
    function_count = 0
    dependency_edges = 0
    for path, source in sorted(files.items()):
        tree = ast.parse(source, filename=path)
        function_count += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
        )
        dependency_edges += sum(
            len(node.names)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            else 0
            for node in ast.walk(tree)
        )
    topology = {
        "dependency_edges": dependency_edges,
        "file_count": len(files),
        "function_count": function_count,
    }

    def transition_source(seed: str) -> dict[str, Any]:
        horizon = 4
        initial_phase = topology["function_count"] % 2
        initial_carry = topology["dependency_edges"] % 2
        trace = [int(seed[index], 16) % 2 for index in range(horizon)]
        phase = initial_phase
        carry = initial_carry
        for drive in trace:
            phase, carry = phase ^ drive, phase if drive else carry
        return {
            "kind": "transition",
            "state": ["phase", "carry"],
            "inputs": ["drive"],
            "gates": [
                {
                    "op": "xor",
                    "out": "next_phase",
                    "args": ["phase", "drive"],
                },
                {
                    "op": "mux",
                    "out": "next_carry",
                    "args": ["drive", "phase", "carry"],
                },
            ],
            "next_state": [
                ["phase", "next_phase"],
                ["carry", "next_carry"],
            ],
            "horizon": horizon,
            "initial": [
                ["phase", initial_phase],
                ["carry", initial_carry],
            ],
            "input_assertions": [
                [time, "drive", value]
                for time, value in enumerate(trace[:-1])
            ],
            "final": [["phase", phase], ["carry", carry]],
            "relations": [],
            "clauses": [],
        }

    def parity_contradiction(names: tuple[str, ...]) -> dict[str, Any]:
        clauses: list[list[list[Any]]] = []
        for rhs in (0, 1):
            for value in range(1 << len(names)):
                bits = [
                    (value >> index) & 1
                    for index in range(len(names))
                ]
                if sum(bits) % 2 == rhs:
                    continue
                clauses.append(
                    [
                        [name, 1 - bit]
                        for name, bit in zip(names, bits)
                    ]
                )
        return {
            "kind": "circuit",
            "inputs": list(names),
            "gates": [],
            "assertions": [],
            "relations": [],
            "clauses": clauses,
        }

    training_seed = hashlib.sha256(
        f"{parent_digest}:training".encode("utf-8")
    ).hexdigest()
    sources = {
        "sat_training": transition_source(training_seed),
        "sat_held_out": transition_source(parent_digest),
        "unsat_training": parity_contradiction(
            ("a", "b", "c", "d", "e", "f")
        ),
        "unsat_held_out": parity_contradiction(
            ("u", "v", "w", "x", "y", "z")
        ),
    }
    body = {
        "schema": "cassimindfield.paired-reasoning-task.v1",
        "source_world": "python-architecture",
        "target_world": "cassifi-exact-constraint-reasoning",
        "parent_source_digest": parent_digest,
        "topology": topology,
        "sources": sources,
        "causal_prediction": {
            "sat_held_out": {
                "status": "sat",
                "evidence": "source-checked-witness",
            },
            "unsat_held_out": {
                "status": "unsat",
                "evidence": "independently-audited-certificate",
            },
        },
    }
    return {**body, "task_sha256": digest(body)}


def independent_reasoning_regime(method: str) -> str:
    return "algebraic" if method.startswith("algebraic") else "conflict"


def independent_reasoning_method(
    source: Mapping[str, Any],
    mode: str,
    *,
    transition_budget: int = 20_000,
) -> dict[str, Any]:
    from cassi_computation_policy import audit_result, compile_source
    from cassi_constraint_field import ConstraintField, ConstraintFieldProfile

    require(
        mode in {"local", "conflict", "algebraic"},
        f"unknown reasoning regime: {mode}",
    )
    compiled = compile_source(source)
    algebraic = mode == "algebraic"
    max_augmentations = (
        min(64, max(0, 262_144 - len(compiled.clauses)))
        if algebraic
        else 0
    )
    profile = ConstraintFieldProfile(
        max_variables=compiled.variables,
        max_clauses=max(1, len(compiled.clauses) + max_augmentations),
        max_transitions=transition_budget,
        max_learned_clauses=64,
        mode=mode,
        controller=False,
        controller_size=8,
        max_hybrid_lines=(
            max(1, min(4096, len(compiled.clauses) * 4 + 16))
            if algebraic
            else 1
        ),
        max_hybrid_transitions=transition_budget,
        max_parity_width=min(8, max(3, compiled.variables)),
        max_resolution_inferences=2048,
        max_augmentations=max_augmentations,
        max_augmentation_arity=2 if algebraic else 1,
    )
    field = ConstraintField(profile)
    state = field.initial(compiled)
    transitions = 0
    while field.status(state) == "running":
        state, _ = field.step(state)
        transitions += 1
        require(
            transitions <= transition_budget,
            "reasoning regime exceeded its transition bound",
        )
    result = field.result(state)
    audit = audit_result(compiled, result)
    certificate = None
    if result["status"] == "unsat":
        if result.get("resolution_proof") is not None:
            certificate = {
                "kind": "resolution",
                "backend_clauses": result["backend_clauses"],
                "learned_clauses": result["learned_clauses"],
                "proof": result["resolution_proof"],
            }
        elif result.get("hybrid_proof") is not None:
            certificate = {
                "kind": "hybrid",
                "proof": result["hybrid_proof"],
            }
        else:
            raise AssertionError("UNSAT reasoning result has no certificate")
    return {
        "mode": mode,
        "compiled_problem_sha256": compiled.sha256,
        "compiled_variables": compiled.variables,
        "compiled_clauses": len(compiled.clauses),
        "status": result["status"],
        "reason": result["reason"],
        "witness": result.get("witness"),
        "certificate": certificate,
        "audit": audit,
        "work": result["work"],
        "field_transitions": transitions,
    }


def independent_reasoning_evidence(
    task: Mapping[str, Any],
    *,
    budget: int = 256,
) -> dict[str, Any]:
    from cassi_computation_policy import (
        METHODS,
        compile_source,
        initial_policy,
        select_method,
        solve_and_learn,
    )

    sources = task["sources"]
    policy = initial_policy()
    training: list[dict[str, Any]] = []
    for family in ("sat", "unsat"):
        source = sources[f"{family}_training"]
        for method in METHODS:
            policy, result = solve_and_learn(
                policy,
                source,
                budget=budget,
                learn=True,
                method=method,
            )
            context = result["context"]
            training.append(
                {
                    "family": family,
                    "method": result["method"],
                    "source_sha256": result["source_sha256"],
                    "context_key": context["context_key"],
                    "structural_context_key": context[
                        "structural_context_key"
                    ],
                    "status": result["status"],
                    "reason": result["reason"],
                    "budget_used": result["budget_used"],
                    "audit_status": result["audit"]["status"],
                }
            )
    held_out: dict[str, Any] = {}
    for family in ("sat", "unsat"):
        training_source = compile_source(sources[f"{family}_training"])
        source = sources[f"{family}_held_out"]
        compiled = compile_source(source)
        training_context = {
            row["context_key"]
            for row in training
            if row["family"] == family
        }
        trained_method, trained_selection = select_method(
            policy,
            compiled,
            budget=budget,
            explore=False,
        )
        fresh_method, fresh_selection = select_method(
            initial_policy(),
            compiled,
            budget=budget,
            explore=False,
        )
        require(
            training_context
            == {trained_selection["evidence_context_key"]},
            f"{family} evidence context did not transfer",
        )
        local = independent_reasoning_method(source, "local")
        trained_regime = independent_reasoning_regime(trained_method)
        fresh_regime = independent_reasoning_regime(fresh_method)
        if local["status"] in {"sat", "unsat"}:
            selected_regime = "local"
            selected_execution = local
            selection_reason = "local-propagation-completed"
        else:
            selected_regime = trained_regime
            selected_execution = independent_reasoning_method(
                source,
                selected_regime,
            )
            selection_reason = "learned-exact-policy-after-local-stall"
        fresh_execution = (
            local
            if local["status"] in {"sat", "unsat"}
            else independent_reasoning_method(source, fresh_regime)
        )
        held_out[family] = {
            "source_sha256": compiled.sha256,
            "training_source_sha256": training_source.sha256,
            "local_screen": local,
            "trained_regime": trained_regime,
            "trained_selection_phase": trained_selection["phase"],
            "trained_evidence_context_key": trained_selection[
                "evidence_context_key"
            ],
            "fresh_regime": fresh_regime,
            "fresh_selection_phase": fresh_selection["phase"],
            "selected_regime": selected_regime,
            "selection_reason": selection_reason,
            "selected_execution": selected_execution,
            "fresh_execution": fresh_execution,
        }
    saving = (
        held_out["unsat"]["fresh_execution"]["field_transitions"]
        - held_out["unsat"]["selected_execution"]["field_transitions"]
    )
    return {
        "budget": budget,
        "training": training,
        "held_out": held_out,
        "unsat_field_transition_saving": saving,
    }

def parent_workspace() -> dict[str, str]:
    return {
        "src/core.py": "def add(value):\n    return value + 1\n",
        "src/runtime.py": "from core import add\n\n\ndef run(value):\n    return add(value)\n",
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_sha(value: Any, key: str, label: str) -> None:
    require(isinstance(value, Mapping) and isinstance(value.get(key), str), f"{label} has no {key}")
    body = {k: v for k, v in value.items() if k != key}
    require(value[key] == digest(body), f"{label} {key} mismatch")


def stable_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key not in {"content_sha256", "wall_ns", "created_wall_ns"}}


def run_cli(lab: Path, args: list[str], expected: int = 0) -> tuple[str, str]:
    completed = subprocess.run(
        [sys.executable, str(lab), *args],
        cwd=str(lab.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != expected:
        raise RuntimeError(
            f"campaign command returned {completed.returncode}, expected {expected}: "
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed.stdout, completed.stderr


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def reference_research_space(parent_digest: str) -> dict[str, Any]:
    prefix = f"architecture-question:{parent_digest[:24]}"
    return {
        "schema": "cassimindfield.architecture-research-space.v2",
        "question_options": [
            {
                "question_id": f"{prefix}:module-boundary-v1",
                "question": "Which bounded module-boundary adapter preserves the observed baseline and holdout contract?",
                "compiler_family": "module-boundary-v1",
                "priority": 1.0,
                "variant_catalog": [
                    {
                        "variant_key": "import-alias",
                        "hypothesis_suffix": "import-alias",
                        "replacement": "return value + bias",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a bounded import alias preserves the API successor contract",
                    },
                    {
                        "variant_key": "import-alias-drift",
                        "hypothesis_suffix": "import-alias-drift",
                        "replacement": "return value + bias + 1",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "an aliased module boundary with an offset remains a candidate for rejection",
                    },
                ],
            },
            {
                "question_id": f"{prefix}:api-successor-v1",
                "question": "Which bounded API-successor architecture preserves the observed baseline and holdout contract?",
                "compiler_family": "api-successor-v1",
                "priority": 1.0,
                "variant_catalog": [
                    {
                        "variant_key": "clean-cutover",
                        "hypothesis_suffix": "clean-cutover",
                        "replacement": "return value + bias",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a synthesized API successor preserves the baseline holdout",
                    },
                    {
                        "variant_key": "offset-drift",
                        "hypothesis_suffix": "offset-drift",
                        "replacement": "return value + bias + 1",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "an offset successor remains a candidate for rejection",
                    },
                ],
            },
            {
                "question_id": f"{prefix}:facade-adapter-v1",
                "question": "Which bounded facade-adapter architecture preserves the observed baseline and holdout contract?",
                "compiler_family": "facade-adapter-v1",
                "priority": 1.0,
                "variant_catalog": [
                    {
                        "variant_key": "facade-cutover",
                        "hypothesis_suffix": "facade-cutover",
                        "replacement": "return value + bias",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a new facade module retargets the public adapter without changing behavior",
                    },
                    {
                        "variant_key": "facade-offset-drift",
                        "hypothesis_suffix": "facade-offset-drift",
                        "replacement": "return value + bias + 1",
                        "expected_holdout": {"increment_2_1": 3},
                        "claim": "a facade cutover with an offset remains a candidate for rejection",
                    },
                ],
            },
        ],
        "source_paths": sorted(parent_workspace()),
        "parent_source_digest": parent_digest,
        "bounded": True,
        "max_variants": MAX_VARIANTS,
    }

def reference_ir(parent_digest: str) -> dict[str, Any]:
    return {
        "schema": "cassimindfield.architecture-ir.v1",
        "version": 1,
        "components": [
            {"id": "core", "module": "src/core_math.py", "kind": "module", "symbols": ["increment"]},
            {"id": "runtime", "module": "src/runtime.py", "kind": "runtime", "symbols": ["run"]},
            {"id": "api", "module": "src/api.py", "kind": "adapter", "symbols": ["execute"]},
        ],
        "interfaces": [
            {"id": "core_runtime", "provider": "core", "consumers": ["runtime"], "symbols": ["increment"], "protocol": "python-import"},
            {"id": "runtime_api", "provider": "runtime", "consumers": ["api"], "symbols": ["run"], "protocol": "python-import"},
        ],
        "state_ownership": [{"id": "runtime_state", "owner": "runtime", "path": "src/runtime.py", "kind": "runtime"}],
        "flows": [
            {"id": "core_to_runtime", "source": "core", "target": "runtime", "interface": "core_runtime", "kind": "call"},
            {"id": "runtime_to_api", "source": "runtime", "target": "api", "interface": "runtime_api", "kind": "call"},
        ],
        "invariants": [
            {"id": "all_python_parses", "kind": "syntax", "description": "Every successor module parses as Python.", "paths": ["src/core_math.py", "src/runtime.py", "src/api.py"]},
            {"id": "one_runtime_owner", "kind": "ownership", "description": "Runtime state has exactly one owner.", "paths": ["src/runtime.py"]},
        ],
        "operations": [
            {"id": "move_core", "kind": "move_module", "source": "src/core.py", "target": "src/core_math.py"},
            {"id": "rename_add", "kind": "symbol_rename", "old_name": "add", "new_name": "increment", "paths": ["src/core_math.py", "src/runtime.py"]},
            {"id": "migrate_increment", "kind": "signature_migration", "path": "src/core_math.py", "symbol": "increment", "old_signature": "def increment(value):", "new_signature": "def increment(value, bias=1):"},
            {"id": "use_bias", "kind": "source_replacement", "path": "src/core_math.py", "find": "return value + 1", "replace": "return value + bias", "expected_count": 1},
            {"id": "retarget_import", "kind": "source_replacement", "path": "src/runtime.py", "find": "from core import increment", "replace": "from core_math import increment", "expected_count": 1},
            {"id": "create_api", "kind": "create_module", "path": "src/api.py", "component": "api", "source": "from runtime import run\n\n\ndef execute(value):\n    return run(value)\n"},
        ],
        "proof_obligations": [
            {"id": "parse_successor", "kind": "parse", "description": "The synthesized successor parses independently.", "target": "all_python_parses"},
            {"id": "digest_stable", "kind": "digest", "description": "Repeated synthesis has one source digest.", "target": "create_api"},
            {"id": "owner_unique", "kind": "ownership", "description": "State owner uniqueness remains true.", "target": "one_runtime_owner"},
        ],
        "migration": {
            "source_revision": "predecessor-v13",
            "target_revision": "architecture-v1",
            "strategy": "clean_cutover",
            "compatibility": "breaking",
            "notes": "Move the core into an explicit successor API.",
            "source_digest": parent_digest,
        },
    }


def expected_architecture(parent_digest: str, family: str, variant: Mapping[str, Any]) -> dict[str, Any]:
    architecture = json.loads(canonical(reference_ir(parent_digest)).decode("utf-8"))
    replacement = variant.get("replacement")
    require(family in FAMILIES and isinstance(replacement, str), f"unsupported reference family {family}")
    for operation in architecture["operations"]:
        if operation.get("id") == "use_bias":
            operation["replace"] = replacement
        elif family == "module-boundary-v1" and operation.get("id") == "retarget_import":
            operation["replace"] = "from core_math import increment as _increment"
    if family == "module-boundary-v1":
        index = next(index for index, op in enumerate(architecture["operations"]) if op.get("id") == "create_api")
        architecture["operations"].insert(index, {
            "id": "runtime_alias_call",
            "kind": "source_replacement",
            "path": "src/runtime.py",
            "find": "return increment(value)",
            "replace": "return _increment(value)",
            "expected_count": 1,
        })
    elif family == "facade-adapter-v1":
        architecture["components"].append({
            "id": "facade",
            "module": "src/facade.py",
            "kind": "adapter",
            "symbols": ["increment"],
        })
        architecture["interfaces"].append({
            "id": "facade_runtime",
            "provider": "facade",
            "consumers": ["runtime"],
            "symbols": ["increment"],
            "protocol": "python-import",
        })
        architecture["flows"].append({
            "id": "facade_to_runtime",
            "source": "facade",
            "target": "runtime",
            "interface": "facade_runtime",
            "kind": "call",
        })
        for invariant in architecture["invariants"]:
            if invariant.get("id") == "all_python_parses":
                invariant["paths"].append("src/facade.py")
        architecture["proof_obligations"].append({
            "id": "facade_created",
            "kind": "behavior",
            "description": "The synthesized facade module is present and on the runtime call path.",
            "target": "create_facade",
        })
        architecture["operations"].extend([
            {
                "id": "create_facade",
                "kind": "create_module",
                "path": "src/facade.py",
                "component": "facade",
                "source": "from core_math import increment as _increment\n\n\ndef increment(value, bias=1):\n    return _increment(value, bias=bias)\n",
            },
            {
                "id": "retarget_runtime_facade",
                "kind": "source_replacement",
                "path": "src/runtime.py",
                "find": "from core_math import increment",
                "replace": "from facade import increment",
                "expected_count": 1,
            },
        ])
    return architecture


def rename_tokens(source: str, old: str, new: str, path: str) -> str:
    tree = ast.parse(source, filename=path)
    del tree
    lines = source.splitlines(keepends=True)
    hits: list[tuple[int, int, int]] = []
    import tokenize
    import io
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string == old:
            hits.append((token.start[0] - 1, token.start[1], token.end[1]))
    require(hits, f"independent rename found no {old!r} in {path}")
    for line_index, start, end in reversed(hits):
        lines[line_index] = lines[line_index][:start] + new + lines[line_index][end:]
    result = "".join(lines)
    ast.parse(result, filename=path)
    return result


def replace_once(source: str, find: str, replacement: str, path: str) -> str:
    require(source.count(find) == 1, f"independent replacement cardinality failed in {path}")
    result = source.replace(find, replacement, 1)
    ast.parse(result, filename=path)
    return result


def reduce_ir(parent: Mapping[str, str], architecture: Mapping[str, Any]) -> dict[str, str]:
    files = dict(parent)
    for operation in architecture.get("operations", []):
        kind = operation.get("kind")
        if kind == "move_module":
            require(operation["source"] in files and operation["target"] not in files, f"independent move refused: {operation.get('id')}")
            files[operation["target"]] = files.pop(operation["source"])
        elif kind == "symbol_rename":
            for path in operation["paths"]:
                files[path] = rename_tokens(files[path], operation["old_name"], operation["new_name"], path)
        elif kind == "signature_migration":
            require(operation["path"] in files, f"independent signature path missing: {operation.get('id')}")
            files[operation["path"]] = replace_once(files[operation["path"]], operation["old_signature"], operation["new_signature"], operation["path"])
        elif kind == "source_replacement":
            require(operation["path"] in files, f"independent source path missing: {operation.get('id')}")
            files[operation["path"]] = replace_once(files[operation["path"]], operation["find"], operation["replace"], operation["path"])
        elif kind == "create_module":
            require(operation["path"] not in files, f"independent create collided: {operation.get('id')}")
            files[operation["path"]] = operation["source"]
        else:
            raise AssertionError(f"independent reducer lacks operation kind {kind!r}")
    return files


def fixed_command(candidate: Path, code: str) -> int:
    completed = subprocess.run([sys.executable, "-c", code], cwd=str(candidate), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=10)
    return completed.returncode


def check_candidate_workspace(candidate: Path, row: Mapping[str, Any], expected_files: Mapping[str, str]) -> None:
    files = {str(path.relative_to(candidate)).replace("\\", "/"): path.read_text(encoding="utf-8") for path in candidate.rglob("*") if path.is_file() and path.name != "__pycache__"}
    require(files == dict(expected_files), f"independent synthesis files differ for {row.get('candidate_id')}")
    for path, source in files.items():
        if path.endswith(".py"):
            ast.parse(source, filename=path)
    baseline_rc = fixed_command(candidate, "import sys;sys.path.insert(0,'src');import api,core_math;assert callable(api.execute);assert callable(core_math.increment);print('baseline-ok')")
    holdout_rc = fixed_command(candidate, "import sys;sys.path.insert(0,'src');from api import execute;assert execute(2)==3;print('holdout-ok')")
    metric = row.get("measurement", {}).get("metric_vector", {})
    require(baseline_rc == metric.get("baseline_returncode") and holdout_rc == metric.get("holdout_returncode"), f"independent measured checks differ for {row.get('candidate_id')}")
    require(baseline_rc == 0, f"baseline check failed for {row.get('candidate_id')}")


def load_field_memory(path: Path) -> Any:
    cassiqwen = ROOT.parent / "CassiQwen"
    cassifi = ROOT.parent / "CassiFI"
    for item in (cassiqwen, cassifi):
        if str(item) not in sys.path:
            sys.path.insert(0, str(item))
    from cassi_field_qwen_workbench import CassiFieldWorkMemory
    return CassiFieldWorkMemory(path)


def field_state_receipt(field_home: Path) -> dict[str, Any]:
    memory = load_field_memory(field_home)
    try:
        return dict(memory.state_receipt())
    finally:
        memory.close()


def semantic_request(operation: str, operation_id: str, **payload: Any) -> dict[str, Any]:
    return {"operation": operation, "operation_id": operation_id, **payload}


def semantic_query(field_home: Path, operation_id: str, reference: Mapping[str, Any]) -> dict[str, Any]:
    memory = load_field_memory(field_home)
    try:
        request = semantic_request("query", operation_id, query={"kind": "record", "reference": dict(reference)})
        response = dict(memory.semantic(request, operation_label=operation_id))
        return {"request": request, "response": response, "result": dict(response.get("result", {}))}
    finally:
        memory.close()


def semantic_agenda(field_home: Path, operation_id: str, goal: Mapping[str, Any], max_items: int) -> dict[str, Any]:
    memory = load_field_memory(field_home)
    try:
        request = semantic_request("autonomous-agenda", operation_id, goal=dict(goal), max_items=max_items)
        response = dict(memory.semantic(request, operation_label=operation_id))
        return {"request": request, "response": response, "result": dict(response.get("result", {}))}
    finally:
        memory.close()

def semantic_register(
    field_home: Path,
    operation_id: str,
    *,
    record_id: str,
    kind: str,
    payload: Mapping[str, Any],
    status: str = "active",
    epistemic_kind: str = "observed",
    dependencies: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Register one probe record and return its exact semantic response."""
    memory = load_field_memory(field_home)
    try:
        request = semantic_request(
            "register",
            operation_id,
            record_id=record_id,
            kind=kind,
            payload=dict(payload),
            status=status,
            epistemic_kind=epistemic_kind,
            dependencies=[dict(ref) for ref in dependencies],
        )
        response = dict(memory.semantic(request, operation_label=operation_id))
        return {
            "request": request,
            "response": response,
            "result": dict(response.get("result", {})),
            "record": response.get("result", {}).get("record"),
        }
    finally:
        memory.close()


def semantic_history_select(
    field_home: Path,
    operation_id: str,
    candidates: Sequence[Mapping[str, Any]],
    evidence_references: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run history-select with an explicit, bounded evidence contract."""
    memory = load_field_memory(field_home)
    try:
        request = semantic_request(
            "history-select",
            operation_id,
            candidates=[dict(item) for item in candidates],
            evidence={
                "purpose": "assessment-history",
                "references": [dict(ref) for ref in evidence_references],
            },
        )
        response = dict(memory.semantic(request, operation_label=operation_id))
        return {
            "request": request,
            "response": response,
            "result": dict(response.get("result", {})),
        }
    finally:
        memory.close()
def semantic_invoke_procedure(
    field_home: Path,
    operation_id: str,
    *,
    procedure_ref: Mapping[str, Any],
    bindings: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Invoke one resident procedure with the same bounded request in either arm."""

    memory = load_field_memory(field_home)
    try:
        request = semantic_request(
            "invoke-procedure",
            operation_id,
            procedure_ref=dict(procedure_ref),
            bindings=dict(bindings),
            context=dict(context),
        )
        response = dict(memory.semantic(request, operation_label=operation_id))
        return {
            "request": request,
            "response": response,
            "result": dict(response.get("result", {})),
        }
    finally:
        memory.close()




def _probe_candidate(
    field_home: Path,
    operation_suffix: str,
    family: str,
) -> dict[str, Any]:
    """Admit one typed question obligation for an isolated selector probe."""
    response = semantic_register(
        field_home,
        f"independent:{operation_suffix}:candidate:{family}",
        record_id=f"probe-question:{family}",
        kind="Obligation",
        payload={
            "purpose": "probe-question",
            "state": "pending",
            "question_id": f"probe-question:{family}",
            "compiler_family": family,
        },
    )
    record = response["record"]
    require(isinstance(record, Mapping), f"probe candidate record missing for {family}")
    return dict(record)


def _probe_history(
    field_home: Path,
    operation_suffix: str,
    family: str,
    *,
    passes: int,
    misses: int,
) -> dict[str, Any]:
    """Admit one typed resident assessment-history revision."""
    response = semantic_register(
        field_home,
        f"independent:{operation_suffix}:history:{family}",
        record_id=f"probe-assessment-history:{family}",
        kind="Assessment",
        payload={
            "purpose": "assessment-history",
            "state": "resolved",
            "question_id": f"probe-question:{family}",
            "compiler_family": family,
            "attempts": passes + misses,
            "passes": passes,
            "misses": misses,
        },
    )
    record = response["record"]
    require(isinstance(record, Mapping), f"probe history record missing for {family}")
    return dict(record)


def isolated_history_selection_probe(root: Path) -> dict[str, Any]:
    """Prove abstention, preflight exclusion, and a causal history mutation."""
    families = FAMILY_ORDER
    candidates: dict[str, dict[str, Any]] = {}
    for mode in ("fresh", "preflight", "resident"):
        path = root / f"history-{mode}"
        require(not path.exists(), f"history probe path unexpectedly exists: {path}")
        candidates[mode] = {
            family: _probe_candidate(path, f"history-{mode}", family)
            for family in families
        }
    candidate_refs = {
        mode: [
            {
                "candidate_id": family,
                "reference": candidates[mode][family],
            }
            for family in families
        ]
        for mode in candidates
    }

    fresh = semantic_history_select(
        root / "history-fresh",
        "independent:history-fresh:select",
        candidate_refs["fresh"],
        [],
    )["result"]
    require(fresh.get("status") == "waiting" and fresh.get("selected") is None, "fresh history selector did not abstain")
    require(fresh.get("evidence") == {"purpose": "assessment-history", "references": [], "full_dependency_closure": True}, "fresh selector evidence was not empty")

    preflight_refs = []
    for family in families:
        response = semantic_register(
            root / "history-preflight",
            f"independent:history-preflight:assessment:{family}",
            record_id=f"probe-preflight-assessment:{family}",
            kind="Assessment",
            payload={
                "purpose": "architecture-question-preflight",
                "state": "resolved",
                "question_id": f"probe-question:{family}",
                "compiler_family": family,
                "status": "PASS",
                "prediction_error": 0.0,
            },
        )
        record = response["record"]
        require(isinstance(record, Mapping), f"preflight record missing for {family}")
        preflight_refs.append(dict(record))
    preflight = semantic_history_select(
        root / "history-preflight",
        "independent:history-preflight:select",
        candidate_refs["preflight"],
        [],
    )["result"]
    require(preflight.get("status") == "waiting" and preflight.get("selected") is None, "preflight assessments masqueraded as resident history")
    require(preflight.get("evidence", {}).get("references") == [], "preflight evidence was admitted implicitly")
    require(not set(ref.get("id") for ref in preflight_refs) & {ref.get("id") for ref in preflight.get("evidence", {}).get("references", [])}, "preflight reference entered selector evidence")

    initial_history = [
        _probe_history(root / "history-resident", "history-resident-initial", families[0], passes=4, misses=0),
        _probe_history(root / "history-resident", "history-resident-initial", families[1], passes=0, misses=4),
        _probe_history(root / "history-resident", "history-resident-initial", families[2], passes=2, misses=2),
    ]
    before = semantic_history_select(
        root / "history-resident",
        "independent:history-resident:select-before",
        candidate_refs["resident"],
        initial_history,
    )["result"]
    require(before.get("status") == "supported", "resident history selector did not support")
    require(before.get("selected", {}).get("candidate_id") == families[0], "initial resident history selected wrong family")
    require({ref.get("id") for ref in before.get("evidence", {}).get("references", [])} == {ref["id"] for ref in initial_history}, "resident history evidence refs are incomplete")
    revised_history = [
        _probe_history(root / "history-resident", "history-resident-revised", families[0], passes=0, misses=4),
        _probe_history(root / "history-resident", "history-resident-revised", families[1], passes=4, misses=0),
        _probe_history(root / "history-resident", "history-resident-revised", families[2], passes=2, misses=2),
    ]
    after = semantic_history_select(
        root / "history-resident",
        "independent:history-resident:select-after",
        candidate_refs["resident"],
        revised_history,
    )["result"]
    require(after.get("status") == "supported", "revised resident history selector did not support")
    require(after.get("selected", {}).get("candidate_id") == families[1], "mutated resident history did not change selected family")
    require(before.get("selected", {}).get("candidate_id") != after.get("selected", {}).get("candidate_id"), "history mutation left selected family unchanged")
    require({ref.get("content_version") for ref in revised_history} == {2}, "resident history mutation did not create revisions")
    return {
        "fresh": fresh,
        "preflight": preflight,
        "resident_before": before,
        "resident_after": after,
        "selected_before": families[0],
        "selected_after": families[1],
    }



def historical_semantic_response(field_home: Path, operation_id: str, expected_operation: str) -> dict[str, Any]:
    """Recover the exact settled semantic response from copied checkpoints."""
    memory = load_field_memory(field_home)
    try:
        owner_id = "field-qwen:computer-invoke:" + hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
        committed = memory.owner.checkpoints._committed_operation(owner_id)
        require(committed is not None, f"copied field lacks committed semantic operation {operation_id}")
        _, initial_manifest = committed
        initial_generation = int(initial_manifest["generation"])
        matches: list[tuple[int, Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]] = []
        for path in sorted(memory.owner.checkpoints.operations.iterdir()):
            if not path.is_file():
                continue
            try:
                operation_record = json.loads(path.read_text(encoding="utf-8"))
                manifest = memory.owner.checkpoints._manifest(operation_record["manifest_sha256"])
                generation = int(manifest["generation"])
                if generation < initial_generation:
                    continue
                state = memory.owner.checkpoints._load_state(manifest)
                computer = state.computers[0].inspect()
                task = computer.get("task")
                result = task.get("last_result") if isinstance(task, Mapping) else None
                continuation = task.get("continuation") if isinstance(task, Mapping) else None
                if isinstance(result, Mapping) and result.get("operation") == expected_operation and isinstance(continuation, Mapping) and continuation.get("request") is None:
                    matches.append((generation, operation_record, manifest, computer))
            except Exception:
                continue
        require(matches, f"semantic operation {operation_id} was not settled")
        _, record, manifest, computer = min(matches, key=lambda item: item[0])
        result = computer["task"]["last_result"]
        response = {
            "schema": "cassi.field-qwen.semantic-operation.v1",
            "operation": expected_operation,
            "operation_id": operation_id,
            "result": dict(result),
            "field_state_sha256": computer.get("state_sha256"),
            "checkpoint_receipt": None,
        }
        require(isinstance(response["field_state_sha256"], str), f"historical semantic field hash absent for {operation_id}")
        del record, manifest
        return response
    finally:
        memory.close()


def fresh_field_lesion(root: Path, question_ref: Mapping[str, Any]) -> dict[str, Any]:
    path = root / "fresh-field"
    require(not path.exists(), "fresh field lesion path unexpectedly exists")
    before = field_state_receipt(path)
    agenda = semantic_agenda(path, "independent:fresh:agenda", {"kind": "architecture-research-question", "question_option_count": len(FAMILIES), "question_ids": [str(question_ref.get("id"))], "max_goals": 2, "min_error": 0.0}, 4)
    query_status: dict[str, Any]
    try:
        queried = semantic_query(path, "independent:fresh:question-query", question_ref)
        query_status = {"status": queried["result"].get("status"), "result": queried["result"]}
    except Exception as exc:
        query_status = {"status": "ABSTAIN", "error": f"{type(exc).__name__}: {exc}"}
    after = field_state_receipt(path)
    return {"before": before, "agenda": agenda, "query": query_status, "after": after}


def assert_state_semantics(receipt: Mapping[str, Any], state: Mapping[str, Any], parent_digest: str) -> None:
    require(state.get("schema") == STATE_SCHEMA, "redesign state schema mismatch")
    selection = receipt.get("field_selection")
    question = receipt.get("field_question")
    require(isinstance(selection, Mapping) and isinstance(question, Mapping), "field evidence is absent")
    selected = receipt.get("selected_candidate_id")
    require(isinstance(selected, str), "selected candidate absent")
    candidate_dag = state.get("candidate_dag")
    require(isinstance(candidate_dag, list), "state candidate DAG is absent")
    dag_row = next((row for row in candidate_dag if isinstance(row, Mapping) and row.get("candidate_id") == selected), None)
    require(isinstance(dag_row, Mapping), "state candidate DAG omits selected candidate")
    selected_row = next((row for row in receipt.get("candidates", []) if isinstance(row, Mapping) and row.get("candidate_id") == selected), None)
    require(isinstance(selected_row, Mapping), "state selected candidate row absent")
    require(state.get("workspace_digest") == selected_row.get("candidate_source_digest"), "state workspace digest differs from selected source")
    require(state.get("selected_candidate_id") == selected, "state selected candidate differs from receipt")
    require(state.get("field_question_id") == question.get("question_id"), "state question id differs from receipt")
    require(state.get("parent_workspace_digest") == parent_digest, "state parent digest differs")
    require(dag_row.get("child_digest") == selected_row.get("candidate_source_digest"), "state candidate child digest differs")
    migration = receipt.get("field_state_migration")
    require(isinstance(migration, Mapping) and migration.get("schema") == MIGRATION_SCHEMA, "state migration missing")
    require(migration.get("selected_candidate_id") == selected, "state migration selected candidate differs")
    require(migration.get("child_field_state_sha256") == receipt.get("field_state_sha256"), "state migration child differs")


def verify_history_receipt_contract(receipt: Mapping[str, Any]) -> None:
    """Validate the campaign's explicit history evidence and revision contract."""
    history = receipt.get("field_assessment_history")
    question = receipt.get("field_question")
    selection = receipt.get("field_selection")
    require(isinstance(history, Mapping), "assessment-history receipt is absent")
    require(isinstance(question, Mapping) and isinstance(selection, Mapping), "history receipt surfaces are absent")
    selector = history.get("field_learning_selector")
    require(isinstance(selector, Mapping), "field history selector receipt is absent")
    event = history.get("history_selection_event")
    evidence = history.get("history_selection_evidence")
    request = history.get("history_selection_request")
    require(isinstance(event, Mapping) and event.get("kind") == "Event", "history selector event ref is absent")
    require(isinstance(evidence, Mapping) and evidence.get("purpose") == "assessment-history", "history selector evidence contract is absent")
    require(evidence.get("references") == history.get("history_record_refs", []), "history selector evidence refs differ from resident history refs")
    require(evidence.get("full_dependency_closure") is True, "history selector evidence closure is not declared")
    require(isinstance(request, Mapping) and request.get("operation") == "history-select", "history selector request is absent")
    require(request.get("evidence") == {"purpose": "assessment-history", "references": history.get("history_record_refs", [])}, "history selector request evidence differs")
    history_candidates = request.get("candidates")
    require(
        isinstance(history_candidates, list)
        and len(history_candidates) == len(FAMILIES)
        and {item.get("candidate_id") for item in history_candidates if isinstance(item, Mapping)} == FAMILIES,
        "history selector candidates do not cover every compiler family",
    )
    result = selector.get("result")
    require(isinstance(result, Mapping), "history selector result is absent")
    require(result.get("event") == event and result.get("evidence") == evidence, "history selector result is not receipt-bound")
    scores = result.get("scores")
    require(
        isinstance(scores, list)
        and len(scores) == len(FAMILIES)
        and {item.get("compiler_family") for item in scores if isinstance(item, Mapping)} == FAMILIES,
        "history selector scores do not cover every compiler family",
    )
    mode = question.get("history_mode")
    require(mode in {"field-abstention-baseline", "resident-history"}, f"unsupported history mode: {mode!r}")
    selected = result.get("selected")
    if mode == "field-abstention-baseline":
        require(result.get("status") == "waiting" and selected is None, "fresh history selector did not abstain")
        require(not evidence.get("references"), "abstaining selector declared resident history")
    else:
        require(result.get("status") == "supported" and isinstance(selected, Mapping), "resident history selector did not support")
        require(evidence.get("references"), "resident history selector has no evidence refs")
        require(selected.get("candidate_id") == question.get("compiler_family"), "resident selector family differs from question")
    require(question.get("history_selection_event") == event, "question history event differs")
    require(question.get("history_selection_evidence") == evidence, "question history evidence differs")
    require(selection.get("history_selection_event") == event, "selection history event differs")
    require(selection.get("history_selection_evidence") == evidence, "selection history evidence differs")
    historical = history.get("historical_v1_obligation_refs")
    current = history.get("current_v2_obligation_refs")
    require(isinstance(historical, list) and isinstance(current, list) and len(historical) == len(current) == len(FAMILIES), "history obligation revision refs are incomplete")
    require({ref.get("id") for ref in historical} == {ref.get("id") for ref in current}, "history obligation revision ids changed")
    require(all(int(new.get("content_version", 0)) > int(old.get("content_version", 0)) for old, new in zip(historical, current)), "history-priority obligations did not advance revisions")
    require(question.get("historical_v1_obligation_refs") == historical and question.get("current_v2_obligation_refs") == current, "question obligation revision refs differ")
    preflight_rows = history.get("preflight_rows")
    require(
        isinstance(preflight_rows, list)
        and len(preflight_rows) == len(FAMILIES)
        and {row.get("compiler_family") for row in preflight_rows if isinstance(row, Mapping)} == FAMILIES,
        "preflight assessments do not cover every compiler family",
    )
    preflight_ids = {
        row.get("record", {}).get("id")
        for row in preflight_rows
        if isinstance(row, Mapping) and isinstance(row.get("record"), Mapping)
    }
    require(not preflight_ids & {ref.get("id") for ref in evidence.get("references", [])}, "preflight assessment entered resident evidence")


def verify_receipt_semantics(receipt: Mapping[str, Any], parent_digest: str, candidate_root: Path | None = None) -> None:
    require(receipt.get("schema") == RECEIPT_SCHEMA, "receipt schema mismatch")
    check_sha(receipt, "content_sha256", "receipt")
    require(receipt.get("generation") == 1, "receipt generation mismatch")
    require(receipt.get("parent_generation") == 0, "receipt parent generation mismatch")
    candidates = receipt.get("candidates")
    require(isinstance(candidates, list) and len(candidates) >= 2, "receipt candidate set is too small")
    selected = receipt.get("selected_candidate_id")
    require(isinstance(selected, str) and selected in {row.get("candidate_id") for row in candidates if isinstance(row, Mapping)}, "receipt selected candidate is not present")
    question = receipt.get("field_question")
    selection = receipt.get("field_selection")
    require(isinstance(question, Mapping) and question.get("schema") == FIELD_QUESTION_SCHEMA, "field question v2 is absent")
    require(isinstance(selection, Mapping) and selection.get("schema") == FIELD_SELECTION_SCHEMA, "field selection v3 is absent")
    verify_history_receipt_contract(receipt)
    options = question.get("question_options")
    require(isinstance(options, list) and len(options) == len(FAMILIES), "resident question option catalog does not cover every compiler family")
    ids = [item.get("question_id") for item in options if isinstance(item, Mapping)]
    families = [item.get("compiler_family") for item in options if isinstance(item, Mapping)]
    require(len(ids) == len(set(ids)) and len(ids) == len(FAMILIES), "resident question ids are not distinct")
    require(len(families) == len(set(families)) and set(families) == FAMILIES, "resident question families are not distinct")
    expected = reference_research_space(parent_digest)
    expected_summaries = [
        {"question_id": option["question_id"], "question": option["question"], "compiler_family": option["compiler_family"], "variant_keys": [item["variant_key"] for item in option["variant_catalog"]]}
        for option in expected["question_options"]
    ]
    require(len(options) == len(expected["question_options"]) == len(FAMILIES), "bounded catalog question option count differs")
    selected_qid = question.get("question_id")
    selected_family = question.get("compiler_family")
    require(selected_qid in ids and selected_family in FAMILIES, "selected question/family is not catalogued")
    selected_summary = next(item for item in options if item["question_id"] == selected_qid)
    require(selected_summary["compiler_family"] == selected_family, "selected question family mismatch")
    if "selected_question_id" in question:
        require(question.get("selected_question_id") == selected_qid, "selected question id alias disagrees")
    if "selected_question_compiler_family" in question:
        require(question.get("selected_question_compiler_family") == selected_family, "selected question family alias disagrees")
    require(question.get("question") == selected_summary["question"], "selected question text differs from catalog")
    require(isinstance(question.get("selected_question_ref"), Mapping) and str(question["selected_question_ref"].get("id", "")).startswith("redesign-question:"), "selected question reference absent")
    qitems = question.get("bootstrap_agenda_items")
    qselected = question.get("bootstrap_agenda_selected")
    rank = question.get("selected_question_agenda_rank")
    require(isinstance(qitems, list) and qitems, "bootstrap agenda is absent")
    require(isinstance(qselected, Mapping) and isinstance(rank, int) and 0 <= rank < len(qitems), "bootstrap agenda selected/rank missing")
    require(qselected == qitems[rank], "bootstrap agenda rank does not select returned item")
    require(qselected.get("kind") == "resolve-obligation", "bootstrap selected item is not an obligation")
    qref = question.get("selected_question_ref")
    require(isinstance(qref, Mapping) and qselected.get("obligation") == qref, "bootstrap selected obligation differs from question reference")
    source_events = question.get("source_event_refs")
    source_obligations = question.get("source_obligation_refs")
    require(
        isinstance(source_events, list)
        and len(source_events) == len(FAMILIES)
        and all(isinstance(item, Mapping) for item in source_events)
        and len({item.get("id") for item in source_events}) == len(FAMILIES),
        "source event refs do not cover every competing question",
    )
    require(
        isinstance(source_obligations, list)
        and len(source_obligations) == len(FAMILIES)
        and all(isinstance(item, Mapping) for item in source_obligations)
        and len({item.get("id") for item in source_obligations}) == len(FAMILIES),
        "source obligation refs do not cover every competing question",
    )
    require(qselected.get("request", {}).get("record_ref") == qref, "bootstrap selected request does not query selected question")
    require(question.get("source_event_ref") in source_events and question.get("source_obligation_ref") in source_obligations, "selected source mapping is not in the resident source refs")
    require(question.get("selected_question_ref") == question.get("source_obligation_ref"), "selected source obligation is not selected question")
    operation_ids = question.get("operation_ids")
    require(isinstance(operation_ids, list) and len(operation_ids) >= 5 and len(set(operation_ids)) == len(operation_ids), "question operation provenance is incomplete")
    bootstrap_operation_id = question.get("bootstrap_agenda_operation_id") or question.get("agenda_operation_id")
    require(bootstrap_operation_id in operation_ids and question.get("question_query_operation_id") in operation_ids, "question agenda/query operation provenance missing")
    require(question.get("field_state_in_sha256") != question.get("field_state_out_sha256"), "question field state did not advance")
    selected_source_digest = next(row["candidate_source_digest"] for row in candidates if row["candidate_id"] == selected)
    assert_state_semantics(receipt, {"schema": STATE_SCHEMA, "generation": 1, "candidate_dag": [{"candidate_id": selected, "child_digest": selected_source_digest}], "workspace_digest": selected_source_digest, "selected_candidate_id": selected, "field_question_id": selected_qid, "parent_workspace_digest": parent_digest, "field_state_sha256": receipt.get("field_state_sha256")}, parent_digest)

def assert_family_diversity(
    parent_files: Mapping[str, str],
    parent_digest: str,
    expected: Mapping[str, Any],
) -> None:
    representative_ir_digests: set[str] = set()
    representative_source_digests: set[str] = set()
    representative_operation_ids: set[tuple[str, ...]] = set()
    for option in expected["question_options"]:
        family = str(option["compiler_family"])
        variant = option["variant_catalog"][0]
        architecture = expected_architecture(parent_digest, family, variant)
        representative_ir_digests.add(digest(architecture))
        representative_source_digests.add(workspace_digest(reduce_ir(parent_files, architecture)))
        representative_operation_ids.add(tuple(operation["id"] for operation in architecture["operations"]))
    require(len(representative_ir_digests) == len(FAMILIES), "compiler families do not have distinct IR documents")
    require(len(representative_source_digests) == len(FAMILIES), "compiler families do not have distinct source reductions")
    require(len(representative_operation_ids) == len(FAMILIES), "compiler families do not have distinct operation sequences")
    facade_variant = next(
        item
        for option in expected["question_options"]
        if option["compiler_family"] == "facade-adapter-v1"
        for item in option["variant_catalog"]
        if item["variant_key"] == "facade-cutover"
    )
    facade_ir = expected_architecture(parent_digest, "facade-adapter-v1", facade_variant)
    facade_operation_ids = [operation["id"] for operation in facade_ir["operations"]]
    require(facade_operation_ids[-2:] == ["create_facade", "retarget_runtime_facade"], "facade IR operation suffix differs from production contract")
    facade_files = reduce_ir(parent_files, facade_ir)
    require(
        facade_files.get("src/runtime.py") == "from facade import increment\n\n\ndef run(value):\n    return increment(value)\n"
        and facade_files.get("src/facade.py") == "from core_math import increment as _increment\n\n\ndef increment(value, bias=1):\n    return _increment(value, bias=bias)\n",
        "facade source reduction did not create and retarget the runtime adapter",
    )
def _reduced_metric_returncodes(files: Mapping[str, str]) -> tuple[int, int]:
    """Measure the independently reduced workspace with production's probes."""
    with tempfile.TemporaryDirectory(prefix="cassimindfield-preflight-") as temporary:
        candidate = Path(temporary)
        for relative, source in files.items():
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        baseline = fixed_command(
            candidate,
            "import sys;sys.path.insert(0,'src');import api,core_math;assert callable(api.execute);assert callable(core_math.increment);print('baseline-ok')",
        )
        holdout = fixed_command(
            candidate,
            "import sys;sys.path.insert(0,'src');from api import execute;assert execute(2)==3;print('holdout-ok')",
        )
        return baseline, holdout


def verify_preflight_rows(
    receipt: Mapping[str, Any],
    parent_files: Mapping[str, str],
    parent_digest: str,
) -> None:
    """Check every production preflight row against an independent reduction.

    The current production receipt records one representative (the first
    catalog variant) per reference option.  If production begins recording
    every catalog variant, the same checks are applied to every row.
    """
    history = receipt.get("field_assessment_history")
    require(isinstance(history, Mapping), "preflight history is absent")
    rows = history.get("preflight_rows")
    require(isinstance(rows, list), "preflight rows are absent")
    expected = reference_research_space(parent_digest)
    options = expected["question_options"]
    all_pairs = [
        (option, variant)
        for option in options
        for variant in option["variant_catalog"]
    ]
    require(
        len(rows) in {len(options), len(all_pairs)},
        "preflight rows do not match the production representative or full-variant schema",
    )
    row_by_family = {
        row.get("compiler_family"): row
        for row in rows
        if isinstance(row, Mapping)
    }
    require(
        len(row_by_family) == len(rows)
        or len(rows) == len(all_pairs),
        "preflight rows contain duplicate family keys without variant coverage",
    )
    if len(rows) == len(all_pairs):
        row_by_candidate = {
            row.get("candidate_id"): row
            for row in rows
            if isinstance(row, Mapping)
        }
        require(len(row_by_candidate) == len(rows), "preflight candidate ids are absent or duplicated")
        checks = [
            (option, variant, row_by_candidate.get(
                f"architecture-{variant['variant_key']}"
                if option["compiler_family"] == "api-successor-v1"
                else f"architecture-{option['compiler_family']}-{variant['variant_key']}"
            ))
            for option, variant in all_pairs
        ]
    else:
        checks = [
            (option, option["variant_catalog"][0], row_by_family.get(option["compiler_family"]))
            for option in options
        ]
    require(all(row is not None for _, _, row in checks), "preflight rows omit a reference option/variant")
    for option, variant, row in checks:
        family = str(option["compiler_family"])
        variant_key = str(variant["variant_key"])
        architecture = expected_architecture(parent_digest, family, variant)
        rebuilt = reduce_ir(parent_files, architecture)
        expected_id = (
            f"architecture-{variant_key}"
            if family == "api-successor-v1"
            else f"architecture-{family}-{variant_key}"
        )
        require(row.get("compiler_family") == family, f"preflight family differs for {expected_id}")
        require(row.get("question_id") == option["question_id"], f"preflight question differs for {expected_id}")
        require(row.get("candidate_id") == expected_id, f"preflight candidate id differs for {family}/{variant_key}")
        require(
            row.get("candidate_source_digest") == workspace_digest(rebuilt),
            f"preflight source digest differs for {expected_id}",
        )
        expected_baseline, expected_holdout = _reduced_metric_returncodes(rebuilt)
        measurement = row.get("measurement")
        require(isinstance(measurement, Mapping), f"preflight measurement is absent for {expected_id}")
        require(
            measurement.get("baseline_returncode") == expected_baseline
            and measurement.get("holdout_returncode") == expected_holdout,
            f"preflight metric return codes differ for {expected_id}",
        )
        record = row.get("record")
        require(isinstance(record, Mapping), f"preflight record is absent for {expected_id}")
        expected_record_id = (
            f"redesign-preflight-assessment:{receipt.get('generation')}:{family}"
        )
        require(
            record.get("id") == expected_record_id,
            f"preflight record id differs for {expected_id}",
        )


def verify_candidate_rows(
    receipt: Mapping[str, Any],
    parent_files: Mapping[str, str],
    parent_digest: str,
    generation_dir: Path,
) -> None:
    expected = reference_research_space(parent_digest)
    assert_family_diversity(parent_files, parent_digest, expected)
    verify_preflight_rows(receipt, parent_files, parent_digest)
    question = receipt["field_question"]
    selected_family = question["compiler_family"]
    selected_option = next(option for option in reference_research_space(parent_digest)["question_options"] if option["question_id"] == question["question_id"])
    selected_catalog = {item["variant_key"]: item for item in selected_option["variant_catalog"]}
    rows = receipt["candidates"]
    require(len(rows) == len(selected_catalog), "candidate count differs from selected field catalog")
    seen: set[str] = set()
    source_digests: set[str] = set()
    for row in rows:
        require(isinstance(row, Mapping), "candidate row is not an object")
        candidate_id = row.get("candidate_id")
        require(isinstance(candidate_id, str) and candidate_id not in seen, "candidate id is absent or duplicated")
        seen.add(candidate_id)
        hypothesis = row.get("hypothesis")
        require(isinstance(hypothesis, Mapping), f"hypothesis missing for {candidate_id}")
        require(hypothesis.get("question_id") == question["question_id"] and hypothesis.get("compiler_family") == selected_family, f"candidate {candidate_id} does not carry selected question family")
        require(hypothesis.get("field_question_origin") == "field-originated-architecture-question" and hypothesis.get("agenda_origin") == "field-owned-architecture-hypothesis", f"candidate {candidate_id} is not field-originated")
        require(hypothesis.get("parent_source_digest") == parent_digest and row.get("parent_source_digest") == parent_digest, f"candidate {candidate_id} parent provenance mismatch")
        variant_key = hypothesis.get("variant_key")
        require(variant_key in selected_catalog, f"candidate {candidate_id} is outside selected catalog")
        variant = selected_catalog[variant_key]
        expected_id = f"architecture-{variant_key}" if selected_family == "api-successor-v1" else f"architecture-{selected_family}-{variant_key}"
        require(candidate_id == expected_id, f"candidate {candidate_id} is not deterministic for {selected_family}/{variant_key}")
        require(hypothesis.get("expected_holdout") == variant["expected_holdout"], f"candidate {candidate_id} holdout expectation differs")
        architecture = hypothesis.get("architecture")
        require(isinstance(architecture, Mapping), f"candidate {candidate_id} architecture missing")
        expected_ir = expected_architecture(parent_digest, selected_family, variant)
        require(architecture == expected_ir, f"candidate {candidate_id} IR differs from independent family synthesis")
        rebuilt = reduce_ir(parent_files, architecture)
        source_digest = row.get("candidate_source_digest")
        require(isinstance(source_digest, str) and source_digest not in source_digests, f"candidate {candidate_id} source digest is absent or duplicated")
        source_digests.add(source_digest)
        require(workspace_digest(rebuilt) == source_digest, f"candidate {candidate_id} independent source digest differs")
        candidate_dir = generation_dir / "candidates" / candidate_id
        check_candidate_workspace(candidate_dir, row, rebuilt)
        manifest = row.get("candidate_manifest")
        require(isinstance(manifest, Mapping), f"candidate {candidate_id} manifest absent")
        require(manifest.get("source_digest") == row.get("candidate_source_digest") and manifest.get("input_source_digest") == parent_digest, f"candidate {candidate_id} manifest provenance mismatch")
        require(manifest.get("ir_digest") == digest(architecture), f"candidate {candidate_id} IR manifest digest mismatch")
        require(manifest.get("operation_ids") == [operation.get("id") for operation in architecture["operations"]], f"candidate {candidate_id} operation manifest mismatch")
        files_manifest = manifest.get("files")
        expected_manifest_files = {
            path: {"bytes": len(content.encode("utf-8")), "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
            for path, content in rebuilt.items()
        }
        require(isinstance(files_manifest, Mapping) and files_manifest == expected_manifest_files, f"candidate {candidate_id} file manifest mismatch")
        source_index = row.get("observatory_index")
        require(isinstance(source_index, Mapping) and isinstance(source_index.get("files"), list), f"candidate {candidate_id} observatory index mismatch")
        indexed = {entry.get("path"): entry for entry in source_index["files"] if isinstance(entry, Mapping)}
        require(set(indexed) == set(rebuilt), f"candidate {candidate_id} observatory file coverage mismatch")
        for path, content in rebuilt.items():
            entry = indexed[path]
            require(entry.get("source_sha256") == hashlib.sha256(content.encode("utf-8")).hexdigest() and entry.get("byte_length") == len(content.encode("utf-8")), f"candidate {candidate_id} observatory source mismatch for {path}")
        metric = row.get("measurement", {}).get("metric_vector", {})
        require(metric.get("baseline_returncode") == 0 and metric.get("holdout_returncode") in {0, 1}, f"candidate {candidate_id} measured checks failed")
        require(row.get("field_assessment", {}).get("record", {}).get("id") == f"redesign-assessment:{candidate_id}", f"candidate {candidate_id} assessment record missing")
    require({row.get("hypothesis", {}).get("compiler_family") for row in rows} == {selected_family}, "candidate rows mix selected and unselected compiler families")
    require(selected_family in FAMILIES and set(selected_catalog) <= {item["variant_key"] for option in expected["question_options"] for item in option["variant_catalog"]}, "candidate family catalog is not independently bounded")
    require(len(source_digests) == len(rows), "candidate source reductions are not diverse")


def verify_direct_facade_campaign(lab: Path, parent_digest: str) -> dict[str, Any]:
    """Run the production campaign with resident history selecting facade directly."""
    expected = reference_research_space(parent_digest)
    with tempfile.TemporaryDirectory(prefix="cassimindfield-facade-verify-") as temporary:
        home = Path(temporary) / "campaign"
        field_home = home / "field"
        for option in expected["question_options"]:
            family = str(option["compiler_family"])
            attempts = 8
            passes = attempts if family == "facade-adapter-v1" else 0
            semantic_register(
                field_home,
                f"independent:force-facade-history:{family}",
                record_id=f"redesign-assessment-history:{family}",
                kind="Assessment",
                payload={
                    "purpose": "assessment-history",
                    "state": "resolved",
                    "question_id": option["question_id"],
                    "compiler_family": family,
                    "attempts": attempts,
                    "passes": passes,
                    "misses": attempts - passes,
                },
            )
        run_cli(lab, ["--data-home", str(home), "--campaign"], expected=0)
        current = load_json(home / "current.json")
        require(current.get("generation") == 1, "direct facade campaign did not produce generation 1")
        generation_dir = home / "generations" / "g0001"
        receipt = load_json(generation_dir / "receipt.json")
        parent = load_json(home / "generations" / "g0000" / "receipt.json")
        parent_files = parent_workspace()
        require(parent.get("content_sha256") == digest(stable_receipt(parent)), "direct facade parent receipt digest mismatch")
        require(receipt.get("parent_receipt_sha256") == parent.get("content_sha256"), "direct facade receipt parent digest mismatch")
        require(receipt.get("field_question", {}).get("compiler_family") == "facade-adapter-v1", "resident history did not select facade family")
        verify_receipt_semantics(receipt, parent_digest)
        verify_candidate_rows(receipt, parent_files, parent_digest, generation_dir)
        expected_candidates = {
            "architecture-facade-adapter-v1-facade-cutover",
            "architecture-facade-adapter-v1-facade-offset-drift",
        }
        require({row.get("candidate_id") for row in receipt["candidates"]} == expected_candidates, "direct facade receipt candidate IDs differ")
        return {
            "status": "PASS",
            "selected_candidate_id": receipt["selected_candidate_id"],
            "selected_question_id": receipt["field_question"]["question_id"],
            "field_state_sha256": receipt["field_state_sha256"],
        }


def verify_agendas_and_field(receipt: Mapping[str, Any], home: Path, parent_digest: str) -> None:
    field_question = receipt["field_question"]
    field_selection = receipt["field_selection"]
    field_home = home / "field"
    copied = home / "copied-field"
    shutil.copytree(field_home, copied)
    history = receipt["field_assessment_history"]
    selector = history["field_learning_selector"]
    selector_id = history["history_selection_operation_id"]
    exact_selector = historical_semantic_response(copied, selector_id, "history-select")
    exact_selector_result = exact_selector["result"]
    require(exact_selector_result == selector["result"], "reopened history selector result differs")
    require(exact_selector_result.get("event") == history["history_selection_event"], "reopened history selector event differs")
    require(exact_selector_result.get("evidence") == history["history_selection_evidence"], "reopened history selector evidence differs")
    verify_history_receipt_contract(receipt)
    historical_refs = history["historical_v1_obligation_refs"]
    current_refs = history["current_v2_obligation_refs"]
    old_ids = {ref["id"] for ref in historical_refs}
    current_ids = {ref["id"] for ref in current_refs}
    require(old_ids == current_ids, "bootstrap revision changed obligation identities")
    current_ref_map = {ref["id"]: ref for ref in current_refs}
    history_event = history["history_selection_event"]
    history_ids = {ref["id"] for ref in history.get("history_record_refs", [])}
    preflight_ids = {
        row.get("record", {}).get("id")
        for row in history.get("preflight_rows", [])
        if isinstance(row, Mapping) and isinstance(row.get("record"), Mapping)
    }
    for ref in current_refs:
        queried = semantic_query(copied, f"independent:history-priority:{ref['id']}", ref)
        record = queried["result"].get("record")
        require(isinstance(record, Mapping) and record.get("id") == ref["id"] and record.get("content_version") == ref["content_version"], "current history-priority obligation revision is not resident")
        payload = record.get("payload", {})
        require(payload.get("history_selection_operation_id") == selector_id, "history-priority obligation lost selector provenance")
        dependencies = record.get("dependencies", [])
        dependency_keys = {(item.get("kind"), item.get("id"), item.get("content_version")) for item in dependencies if isinstance(item, Mapping)}
        require((history_event.get("kind"), history_event.get("id"), history_event.get("content_version")) in dependency_keys, "history-priority obligation lacks selector event dependency")
        require(history_ids <= {item.get("id") for item in dependencies if isinstance(item, Mapping)}, "history-priority obligation lacks resident history dependency")
        require(not preflight_ids & {item.get("id") for item in dependencies if isinstance(item, Mapping)}, "preflight assessment entered obligation dependencies")
    agenda_ref_ids = {
        item.get("obligation", {}).get("id")
        for item in field_question["bootstrap_agenda_items"]
        if isinstance(item, Mapping) and isinstance(item.get("obligation"), Mapping)
    }
    require(agenda_ref_ids <= current_ids, "bootstrap agenda uses a stale or foreign obligation revision")
    require(not agenda_ref_ids & old_ids - current_ids, "bootstrap agenda selected historical v1 obligation")
    require(field_question["selected_question_ref"] in current_refs, "selected bootstrap question is not current v2")
    bootstrap_id = field_question.get("bootstrap_agenda_operation_id") or field_question["agenda_operation_id"]
    bootstrap = {"response": historical_semantic_response(copied, bootstrap_id, "autonomous-agenda")}
    bootstrap["result"] = dict(bootstrap["response"]["result"])
    bootstrap_result = bootstrap["result"]
    require(digest(bootstrap_result) == field_question["bootstrap_agenda_result_sha256"], "recorded bootstrap agenda result digest differs")
    require(bootstrap_result.get("agenda") == field_question["bootstrap_agenda_items"] and bootstrap_result.get("selected") == field_question["bootstrap_agenda_selected"], "field-returned bootstrap agenda differs from receipt")
    agenda_items = bootstrap_result["agenda"]
    selected = bootstrap_result["selected"]
    require(isinstance(agenda_items, list) and isinstance(selected, Mapping), "bootstrap replay did not return agenda selection")
    selected_ref = field_question["selected_question_ref"]
    require(selected.get("obligation") == selected_ref, "bootstrap replay selected wrong question obligation")
    candidate = {"response": historical_semantic_response(copied, field_selection["agenda_operation_id"], "autonomous-agenda")}
    candidate["result"] = dict(candidate["response"]["result"])
    candidate_result = candidate["result"]
    require(candidate_result.get("agenda") == field_selection["candidate_agenda_items"] and candidate_result.get("selected") == field_selection["candidate_agenda_selected"], "field-returned candidate agenda differs from receipt")
    candidate_rank = field_selection.get("candidate_agenda_rank", field_selection.get("selected_candidate_rank"))
    require(isinstance(candidate_rank, int) and 0 <= candidate_rank < len(field_selection["candidate_agenda_items"]) and field_selection["candidate_agenda_selected"] == field_selection["candidate_agenda_items"][candidate_rank], "candidate agenda rank does not select returned item")
    candidate_obligations = {item.get("obligation", {}).get("id") for item in field_selection["candidate_agenda_items"] if isinstance(item, Mapping) and str(item.get("obligation", {}).get("id", "")).startswith("redesign-obligation:")}
    candidate_row_ids = {f"redesign-obligation:{row['candidate_id']}" for row in receipt["candidates"]}
    require(candidate_obligations <= candidate_row_ids, "candidate agenda contains an obligation outside candidate rows")
    require(field_selection["candidate_agenda_selected"].get("obligation", {}).get("id") == f"redesign-obligation:{receipt['selected_candidate_id']}", "candidate agenda selected field result differs")
    exact_query_response = historical_semantic_response(copied, field_question["question_query_operation_id"], "query")
    query_request = {"operation": "query", "operation_id": field_question["question_query_operation_id"], "query": {"kind": "record", "reference": dict(selected_ref)}}
    require(digest(query_request) == field_question["question_query_request_sha256"], "question query request digest differs")
    require(digest(exact_query_response) == field_question["question_query_response_sha256"], "question query response digest differs")
    exact_result = exact_query_response.get("result", {})
    exact_record = exact_result.get("record") if isinstance(exact_result, Mapping) else None
    require(isinstance(exact_record, Mapping), "copied historical query has no record")
    require(digest(exact_result) == field_question["question_query_result_sha256"], "question query result digest differs")
    require(digest(exact_record) == field_question["question_query_record_sha256"], "question query record digest differs")
    require(exact_record.get("id") == selected_ref.get("id") and exact_record.get("content_version") == selected_ref.get("content_version"), "historical query returned wrong selected record")
    payload = exact_record.get("payload")
    selected_option = next(option for option in reference_research_space(parent_digest)["question_options"] if option["question_id"] == field_question["question_id"])
    require(isinstance(payload, Mapping) and payload.get("question_id") == field_question["question_id"] and payload.get("compiler_family") == field_question["compiler_family"], "historical query payload does not recover selected question")
    require(payload.get("variant_catalog") == selected_option["variant_catalog"], "historical selected question catalog is not bounded/deterministic")
    require(payload.get("source_event_id") == field_question["source_event_ref"].get("id"), "historical question payload maps to wrong source event")
    require(payload.get("parent_source_digest") == parent_digest, "historical question payload lost parent provenance")
    require(isinstance(exact_record.get("dependencies"), list) and any(isinstance(ref, Mapping) and ref.get("id") == field_question["source_event_ref"].get("id") for ref in exact_record["dependencies"]), "historical question source event dependency absent")
    independent_query = semantic_query(copied, "independent:resident-question-query", selected_ref)
    independent_result = independent_query["result"]
    independent_record = independent_result.get("record")
    require(isinstance(independent_record, Mapping), "current question query returned no record")
    if int(selected_ref.get("content_version", 1)) >= 2:
        require(independent_result.get("status") == "supported", "current history-priority question query was not supported")
        require(independent_record.get("id") == selected_ref.get("id") and independent_record.get("content_version") == selected_ref.get("content_version"), "current question query returned wrong revision")
    else:
        require(independent_result.get("status") in {"support-gap", "stale-or-inactive"}, "post-resolution current/stale relation was not declared")
        current = independent_result.get("current")
        require(isinstance(current, Mapping) and current.get("content_version") == 2 and current.get("id") == selected_ref.get("id"), "query relation to current record is absent")
        require("stale-or-inactive" in set(independent_result.get("limitations", [])), "query did not declare stale relation")
        if "post_resolution_relation" in field_question:
            require(field_question.get("post_resolution_relation") in {"historical_payload_recovered_current_version_stale", "historical_payload_recovered_current_stale"}, "receipt post-resolution stale relation is invalid")
    # Query every admitted question through copied persisted field; no receipt payload is used.
    for item in field_question["bootstrap_agenda_items"]:
        ref = item.get("obligation")
        require(isinstance(ref, Mapping), "question agenda item has no obligation ref")
        queried = semantic_query(copied, "independent:question-option:" + str(ref.get("id")), ref)
        rec = queried["result"].get("record")
        require(isinstance(rec, Mapping) and rec.get("payload", {}).get("question_id") in {option["question_id"] for option in field_question["question_options"]}, "copied field option payload is outside resident catalog")
        option = next(option for option in field_question["question_options"] if option["question_id"] == rec["payload"]["question_id"])
        require(rec["payload"].get("compiler_family") == option["compiler_family"], "copied field option family differs")
        require(isinstance(rec["payload"].get("variant_catalog"), list) and len(rec["payload"]["variant_catalog"]) <= MAX_VARIANTS, "resident variant catalog exceeds bound")
    fresh = fresh_field_lesion(home, selected_ref)
    require(fresh["before"].get("semantic_family_counts", {}).get("Question", 0) == 0 and fresh["before"].get("semantic_family_counts", {}).get("Obligation", 0) == 0, "fresh field lesion was not empty")
    fresh_agenda = fresh["agenda"]["result"]
    question_agenda_items = [item for item in fresh_agenda.get("agenda", []) if isinstance(item, Mapping) and str(item.get("obligation", {}).get("id", "")).startswith("redesign-question:")]
    require(not question_agenda_items and not (isinstance(fresh_agenda.get("selected"), Mapping) and str(fresh_agenda["selected"].get("obligation", {}).get("id", "")).startswith("redesign-question:")), "fresh field returned a resident question")
    fresh_status = str(fresh["query"].get("status"))
    require(fresh_status in {"ABSTAIN", "support-gap", "unsupported", "stale-or-inactive"}, "fresh field query did not abstain/wait")
    if fresh_status == "ABSTAIN":
        lowered = str(fresh["query"].get("error", "")).lower()
        require(any(token in lowered for token in ("unavailable", "missing", "unsupported", "query", "record", "state")), "fresh field abstention has no missing-resident cause")
    probe = isolated_history_selection_probe(home / "isolated-history-probe")
    require(probe["selected_before"] != probe["selected_after"], "isolated history probe did not change selection")
    require(fresh["after"].get("semantic_family_counts", {}).get("Question", 0) == 0 and fresh["after"].get("semantic_family_counts", {}).get("Obligation", 0) == 0, "fresh field recovered a resident question")


def _history_ref_families(refs: Any) -> set[str]:
    if not isinstance(refs, list):
        return set()
    return {
        str(reference.get("id", "")).removeprefix("redesign-assessment-history:")
        for reference in refs
        if isinstance(reference, Mapping)
        and str(reference.get("id", "")).startswith("redesign-assessment-history:")
    }


def verify_history_trajectory_receipts(receipts: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Verify that resident history naturally switches across all families."""
    require(len(receipts) == 3, "multi-cycle trajectory does not contain three receipts")
    families = [
        str(receipt.get("field_question", {}).get("compiler_family"))
        for receipt in receipts
        if isinstance(receipt.get("field_question"), Mapping)
    ]
    require(len(families) == 3 and set(families) == FAMILIES, "history trajectory did not visit each compiler family once")
    for index, receipt in enumerate(receipts):
        generation = index + 1
        check_sha(receipt, "content_sha256", f"generation {generation} receipt")
        require(receipt.get("schema") == RECEIPT_SCHEMA, f"generation {generation} receipt schema changed")
        require(receipt.get("generation") == generation, f"generation {generation} receipt number differs")
        require(receipt.get("parent_generation") == generation - 1, f"generation {generation} parent generation differs")
        if index:
            require(
                receipt.get("parent_receipt_sha256") == receipts[index - 1].get("content_sha256"),
                f"generation {generation} parent receipt binding differs",
            )
        history = receipt.get("field_assessment_history")
        question = receipt.get("field_question")
        selection = receipt.get("field_selection")
        require(isinstance(history, Mapping), f"generation {generation} history receipt is absent")
        require(isinstance(question, Mapping) and isinstance(selection, Mapping), f"generation {generation} selection surfaces are absent")
        trajectory = history.get("history_trajectory")
        require(isinstance(trajectory, Mapping), f"generation {generation} history trajectory is absent")
        family = families[index]
        require(trajectory.get("generation") == generation and trajectory.get("selected_family") == family, f"generation {generation} trajectory binding differs")
        require(trajectory.get("selection_is_field_owned") is True, f"generation {generation} trajectory is not field-owned")
        selector = history.get("field_learning_selector")
        result = selector.get("result") if isinstance(selector, Mapping) else None
        require(isinstance(result, Mapping), f"generation {generation} history selector result is absent")
        selected = result.get("selected")
        if index == 0:
            require(question.get("history_mode") == "field-abstention-baseline", "cycle one did not preserve fresh-field abstention")
            require(trajectory.get("prior_history_families") == [], "cycle one had resident history before seeding")
            require(set(trajectory.get("seeded_families", [])) == FAMILIES - {family}, "cycle one did not seed exactly the unselected families")
            require(set(trajectory.get("resident_history_families_after", [])) == FAMILIES, "cycle one did not leave all family histories resident")
            require(selected is None and not history.get("history_selection_evidence", {}).get("references"), "cycle one history selector unexpectedly selected a resident family")
        else:
            require(question.get("history_mode") == "resident-history", f"cycle {generation} did not use resident history")
            require(set(trajectory.get("prior_history_families", [])) == FAMILIES, f"cycle {generation} did not see all resident histories")
            require(trajectory.get("seeded_families") == [], f"cycle {generation} reseeded an existing family")
            require(set(trajectory.get("resident_history_families_after", [])) == FAMILIES, f"cycle {generation} lost a resident family")
            require(isinstance(selected, Mapping) and selected.get("candidate_id") == family, f"cycle {generation} history selector did not select the measured family")
            evidence = history.get("history_selection_evidence")
            require(isinstance(evidence, Mapping) and _history_ref_families(evidence.get("references")) == FAMILIES, f"cycle {generation} history evidence does not cover all families")
            require(_history_ref_families(history.get("history_record_refs")) == FAMILIES, f"cycle {generation} query did not recover all family histories")
        require(selection.get("method") == "semantic.autonomous-agenda", f"generation {generation} selected outside the field agenda")
        require(selection.get("selected_question_compiler_family") == family, f"generation {generation} selection surface differs from field question")
        require(selection.get("history_selection_event") == history.get("history_selection_event"), f"generation {generation} history event was not receipt-bound")
    return {
        "status": "PASS",
        "families": families,
        "cycle_one_seeded": sorted(
            str(item)
            for item in receipts[0]["field_assessment_history"]["history_trajectory"].get("seeded_families", [])
        ),
    }


def verify_cumulative_successor_lineage(
    home: Path,
    receipts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild the promoted workspace chain from persisted generation bytes."""
    expected_parent = workspace_digest(parent_workspace())
    file_counts: list[int] = []
    for generation, receipt in enumerate(receipts, start=1):
        selected_id = receipt.get("selected_candidate_id")
        require(isinstance(selected_id, str), f"generation {generation} selected candidate is absent")
        selected_row = next(
            (
                row
                for row in receipt.get("candidates", [])
                if isinstance(row, Mapping) and row.get("candidate_id") == selected_id
            ),
            None,
        )
        require(isinstance(selected_row, Mapping), f"generation {generation} selected row is absent")
        candidate_root = home / "generations" / f"g{generation:04d}" / "candidates" / selected_id
        files = {
            path.relative_to(candidate_root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(candidate_root.rglob("*.py"))
            if path.is_file() and "__pycache__" not in path.parts
        }
        child_digest = workspace_digest(files)
        migration = receipt.get("field_state_migration")
        state = load_json(home / "generations" / f"g{generation:04d}" / "state.json")
        require(isinstance(migration, Mapping), f"generation {generation} migration is absent")
        require(selected_row.get("parent_source_digest") == expected_parent, f"generation {generation} candidate did not inherit the promoted predecessor")
        require(migration.get("parent_workspace_digest") == expected_parent, f"generation {generation} migration parent differs")
        require(migration.get("child_workspace_digest") == child_digest, f"generation {generation} migration child differs")
        require(selected_row.get("candidate_source_digest") == child_digest, f"generation {generation} selected digest differs from persisted bytes")
        require(state.get("parent_workspace_digest") == expected_parent, f"generation {generation} state parent differs")
        require(state.get("workspace_digest") == child_digest, f"generation {generation} state child differs")
        if generation > 1:
            hypothesis = selected_row.get("hypothesis")
            require(
                isinstance(hypothesis, Mapping)
                and hypothesis.get("construction_origin") == "field-composed-parent-topology",
                f"generation {generation} was not composed from observed predecessor topology",
            )
            prediction = hypothesis.get("causal_prediction")
            require(
                isinstance(prediction, Mapping)
                and prediction.get("inherited_parent_digest") == expected_parent
                and prediction.get("novel_module") in files,
                f"generation {generation} causal construction prediction is absent",
            )
        file_counts.append(len(files))
        expected_parent = child_digest
    require(file_counts == sorted(file_counts) and len(set(file_counts)) == len(file_counts), "successor generations did not accumulate architecture layers")
    return {
        "status": "PASS",
        "file_counts": file_counts,
        "final_workspace_digest": expected_parent,
    }


def verify_transfer_learning(
    home: Path,
    receipts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Contrast the resident learned method with a matched fresh-field arm."""

    first_selection = receipts[0].get("field_selection", {})
    learning = (
        first_selection.get("learned_investigation_procedure")
        if isinstance(first_selection, Mapping)
        else None
    )
    require(isinstance(learning, Mapping), "executed procedure learning is absent")
    require(learning.get("status") == "supported", "investigation procedure was not learned")
    procedure_ref = learning.get("procedure")
    require(
        isinstance(procedure_ref, Mapping)
        and procedure_ref.get("id") == INVESTIGATION_PROCEDURE_ID,
        "learned procedure reference differs",
    )
    measured_cost = learning.get("measured_cost")
    require(
        isinstance(measured_cost, Mapping)
        and int(measured_cost.get("net_saved_steps", 0)) > 0,
        "procedure learning did not reward investigation economy",
    )
    require(
        len(learning.get("training_preflight_operation_ids", [])) == 2
        and len(learning.get("holdout_preflight_operation_ids", [])) == 1,
        "procedure learning is not bound to two executed traces and one holdout",
    )

    applications: list[dict[str, Any]] = []
    for generation, receipt in enumerate(receipts[1:], start=2):
        selection = receipt.get("field_selection", {})
        application = (
            selection.get("applied_investigation_procedure")
            if isinstance(selection, Mapping)
            else None
        )
        require(
            isinstance(application, Mapping)
            and application.get("status") == "supported",
            f"generation {generation} did not apply the resident procedure",
        )
        require(
            application.get("parent_source_digest")
            == receipt.get("field_state_migration", {}).get(
                "parent_workspace_digest"
            ),
            f"generation {generation} procedure used the wrong predecessor",
        )
        actions = application.get("proposed_actions")
        require(
            isinstance(actions, list)
            and [row.get("op") for row in actions]
            == [
                "locate-binding",
                "compose-operations",
                "compile-successor",
            ],
            f"generation {generation} procedure actions differ",
        )
        require(
            all(
                isinstance(row, Mapping)
                and row.get("candidate") == application.get("candidate_id")
                for row in actions
            ),
            f"generation {generation} procedure did not bind the unfamiliar task",
        )
        for candidate in receipt.get("candidates", []):
            require(
                isinstance(candidate, Mapping),
                f"generation {generation} candidate row is malformed",
            )
            hypothesis = candidate.get("hypothesis")
            causal = (
                hypothesis.get("causal_prediction")
                if isinstance(hypothesis, Mapping)
                else None
            )
            outcome = candidate.get("causal_outcome")
            require(
                isinstance(causal, Mapping) and isinstance(outcome, Mapping),
                f"generation {generation} causal prediction/outcome is absent",
            )
            expected = {
                "baseline_returncode": causal.get(
                    "expected_baseline_returncode"
                ),
                "holdout_returncode": causal.get(
                    "expected_holdout_returncode"
                ),
            }
            observed = candidate.get("measurement", {}).get("prediction", {}).get(
                "observed"
            )
            require(
                outcome.get("expected") == expected
                and outcome.get("observed") == observed
                and outcome.get("matched") == (expected == observed),
                f"generation {generation} causal outcome was not derived from measurement",
            )
        applications.append(dict(application))

    with tempfile.TemporaryDirectory(
        prefix="cassimindfield-procedure-comparison-"
    ) as temporary:
        root = Path(temporary)
        experienced_home = root / "experienced"
        shutil.copytree(home / "field", experienced_home)
        bindings = {
            "role_0": "architecture-unfamiliar-holdout",
        }
        context = {
            "parent_source_digest": receipts[-1]["field_state_migration"][
                "child_workspace_digest"
            ],
            "comparison": "matched-single-invocation",
        }
        experienced = semantic_invoke_procedure(
            experienced_home,
            "independent:experienced-procedure",
            procedure_ref=procedure_ref,
            bindings=bindings,
            context=context,
        )
        experienced_result = experienced["result"]
        require(
            experienced_result.get("status") == "supported"
            and experienced_result.get("proposed_actions"),
            "experienced field did not transfer its procedure",
        )
        fresh_status = "exception"
        fresh_actions: list[Any] = []
        try:
            fresh = semantic_invoke_procedure(
                root / "fresh",
                "independent:fresh-procedure",
                procedure_ref=procedure_ref,
                bindings=bindings,
                context=context,
            )
        except Exception:
            fresh = None
        if isinstance(fresh, Mapping):
            fresh_result = fresh.get("result", {})
            if isinstance(fresh_result, Mapping):
                fresh_status = str(fresh_result.get("status"))
                actions = fresh_result.get("proposed_actions", [])
                if isinstance(actions, list):
                    fresh_actions = actions
        require(
            fresh_status != "supported" and not fresh_actions,
            "fresh field unexpectedly applied resident experience",
        )

    return {
        "status": "PASS",
        "procedure_id": INVESTIGATION_PROCEDURE_ID,
        "training_traces": 2,
        "holdout_traces": 1,
        "net_saved_steps": int(measured_cost["net_saved_steps"]),
        "unfamiliar_successor_applications": len(applications),
        "experienced_status": experienced_result.get("status"),
        "experienced_proposed_actions": len(
            experienced_result.get("proposed_actions", [])
        ),
        "fresh_status": fresh_status,
        "fresh_proposed_actions": len(fresh_actions),
        "matched_invocation_budget": 1,
    }


def verify_cross_world_expansion(
    lab: Path,
    home: Path,
    receipts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconstruct and execute the architecture-to-field-program transfer."""

    stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--cross-world"],
        expected=0,
    )
    summary = json.loads(stdout)
    require(
        summary.get("status") in {"PASS", "REPLAYED"},
        "cross-world campaign did not pass or replay",
    )
    path = home / "cross-world" / "field-program-transfer.json"
    original = path.read_bytes()
    receipt = load_json(path)
    check_sha(receipt, "content_sha256", "cross-world receipt")
    require(
        receipt.get("schema") == CROSS_WORLD_SCHEMA,
        "cross-world receipt schema differs",
    )
    final_generation = receipts[-1]
    selected = final_generation["selected_candidate_id"]
    candidate_root = (
        home
        / "generations"
        / "g0003"
        / "candidates"
        / selected
    )
    files = {
        source.relative_to(candidate_root).as_posix(): source.read_text(
            encoding="utf-8"
        )
        for source in sorted(candidate_root.rglob("*.py"))
        if source.is_file() and "__pycache__" not in source.parts
    }
    parent_digest = workspace_digest(files)
    task = independent_field_program_task(files, parent_digest)
    require(receipt.get("task") == task, "cross-world task is not source-derived")
    require(
        task["source_world"] != task["target_world"],
        "cross-world task did not cross a construction-world boundary",
    )
    source = independent_structured_source(task)
    require(
        receipt.get("structured_source") == source,
        "cross-world structured source is not task-derived",
    )
    execution = independent_execute_field_program(source)
    require(
        receipt.get("execution") == execution,
        "cross-world execution differs from independent execution",
    )
    causal = receipt.get("causal_outcome")
    require(
        isinstance(causal, Mapping)
        and causal.get("expected") == task["causal_prediction"]
        and causal.get("observed") == execution["execution"]
        and causal.get("matched") is True,
        "cross-world causal prediction did not match execution",
    )
    experienced = receipt.get("experienced_procedure")
    fresh = receipt.get("fresh_field_control")
    require(
        isinstance(experienced, Mapping)
        and experienced.get("status") == "supported",
        "experienced field did not transfer across worlds",
    )
    actions = experienced.get("proposed_actions")
    required_plan = [
        "locate-binding",
        "compose-operations",
        "compile-successor",
    ]
    require(
        isinstance(actions, list)
        and [row.get("op") for row in actions] == required_plan
        and all(row.get("candidate") == task["task_sha256"] for row in actions),
        "cross-world transferred plan differs",
    )
    require(
        isinstance(fresh, Mapping)
        and fresh.get("status") != "supported"
        and fresh.get("proposed_actions") == [],
        "fresh field unexpectedly possessed the cross-world procedure",
    )
    comparison = receipt.get("work_comparison")
    require(
        isinstance(comparison, Mapping)
        and comparison.get("metric") == "primitive-plan-steps-examined"
        and comparison.get("experienced", {}).get(
            "primitive_steps_examined"
        )
        == 3
        and comparison.get("fresh_bounded_search", {}).get(
            "primitive_steps_examined"
        )
        == 6
        and comparison.get("net_saved_steps") == 3,
        "cross-world work comparison differs",
    )
    verify_stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--verify-cross-world"],
        expected=0,
    )
    require(
        json.loads(verify_stdout).get("status") == "PASS",
        "production cross-world verification failed",
    )
    replay_stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--cross-world"],
        expected=0,
    )
    require(
        json.loads(replay_stdout).get("status") == "REPLAYED"
        and path.read_bytes() == original,
        "cross-world replay changed the frozen receipt",
    )
    controls: dict[str, str] = {}
    try:
        mutated = load_json(path)
        mutated["structured_source"]["constants"]["BASE"] += 1
        mutated["content_sha256"] = digest(
            {
                key: value
                for key, value in mutated.items()
                if key != "content_sha256"
            }
        )
        path.write_bytes(canonical(mutated) + b"\n")
        failed_stdout, failed_stderr = run_cli(
            lab,
            ["--data-home", str(home), "--verify-cross-world"],
            expected=2,
        )
        require(
            any(
                token in (failed_stdout + failed_stderr).lower()
                for token in ("structured source", "task ir", "diverged")
            ),
            "cross-world source mutation did not fire",
        )
        controls["source_mutation"] = "PASS"
    finally:
        path.write_bytes(original)
    try:
        mutated = load_json(path)
        mutated["experienced_procedure"]["proposed_actions"] = list(
            reversed(
                mutated["experienced_procedure"]["proposed_actions"]
            )
        )
        mutated["content_sha256"] = digest(
            {
                key: value
                for key, value in mutated.items()
                if key != "content_sha256"
            }
        )
        path.write_bytes(canonical(mutated) + b"\n")
        failed_stdout, failed_stderr = run_cli(
            lab,
            ["--data-home", str(home), "--verify-cross-world"],
            expected=2,
        )
        require(
            any(
                token in (failed_stdout + failed_stderr).lower()
                for token in ("construction plan", "work comparison", "wrong")
            ),
            "cross-world plan mutation did not fire",
        )
        controls["plan_mutation"] = "PASS"
    finally:
        path.write_bytes(original)
    require(
        set(controls) == {"source_mutation", "plan_mutation"},
        "cross-world mutation controls are incomplete",
    )
    return {
        "status": "PASS",
        "task_sha256": task["task_sha256"],
        "source_world": task["source_world"],
        "target_world": task["target_world"],
        "experienced_status": experienced["status"],
        "fresh_status": fresh["status"],
        "net_saved_steps": comparison["net_saved_steps"],
        "execution": execution["execution"],
        "replay": "PASS",
        "controls": controls,
    }


def verify_constraint_world_expansion(
    lab: Path,
    home: Path,
    receipts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild, enumerate, solve, and mutate the constraint-world transfer."""

    stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--constraint-world"],
        expected=0,
    )
    summary = json.loads(stdout)
    require(
        summary.get("status") in {"PASS", "REPLAYED"},
        "constraint-world campaign did not pass or replay",
    )
    path = home / "cross-world" / "constraint-transfer.json"
    original = path.read_bytes()
    receipt = load_json(path)
    check_sha(receipt, "content_sha256", "constraint-world receipt")
    require(
        receipt.get("schema") == CONSTRAINT_WORLD_SCHEMA,
        "constraint-world receipt schema differs",
    )
    final_generation = receipts[-1]
    selected = final_generation["selected_candidate_id"]
    candidate_root = (
        home
        / "generations"
        / "g0003"
        / "candidates"
        / selected
    )
    files = {
        source.relative_to(candidate_root).as_posix(): source.read_text(
            encoding="utf-8"
        )
        for source in sorted(candidate_root.rglob("*.py"))
        if source.is_file() and "__pycache__" not in source.parts
    }
    parent_digest = workspace_digest(files)
    task = independent_constraint_task(files, parent_digest)
    require(
        receipt.get("task") == task,
        "constraint-world task is not source-derived",
    )
    require(
        task["source_world"] != task["target_world"],
        "constraint task did not cross a construction-world boundary",
    )
    source = independent_constraint_source(task)
    require(
        receipt.get("constraint_source") == source,
        "constraint source is not task-derived",
    )
    models = independent_constraint_models(source)
    require(models, "independent enumeration found no constraint witness")
    execution = independent_execute_constraint(source)
    require(
        receipt.get("execution") == execution,
        "constraint execution differs from independent execution",
    )
    witness = execution["witness"]
    expected_witness_keys = {
        "phase@0",
        "carry@0",
        *{
            f"drive@{time}"
            for time in range(int(source["horizon"]))
        },
    }
    require(
        set(witness) == expected_witness_keys,
        "constraint witness escaped the declared boundary",
    )
    solved_trace = [
        int(witness[f"drive@{time}"])
        for time in range(int(source["horizon"]))
    ]
    require(
        solved_trace in models,
        "constraint witness is absent from independent model enumeration",
    )
    causal = receipt.get("causal_outcome")
    expected_observation = {
        "status": execution["status"],
        "final": execution["witness_audit"]["final"],
        "witness_required": bool(execution["witness"]),
    }
    require(
        isinstance(causal, Mapping)
        and causal.get("expected") == task["causal_prediction"]
        and causal.get("observed") == expected_observation
        and causal.get("matched") is True,
        "constraint causal prediction did not match execution",
    )
    experienced = receipt.get("experienced_procedure")
    fresh = receipt.get("fresh_field_control")
    required_plan = [
        "locate-binding",
        "compose-operations",
        "compile-successor",
    ]
    actions = (
        experienced.get("proposed_actions")
        if isinstance(experienced, Mapping)
        else None
    )
    require(
        isinstance(experienced, Mapping)
        and experienced.get("status") == "supported"
        and isinstance(actions, list)
        and [row.get("op") for row in actions] == required_plan
        and all(row.get("candidate") == task["task_sha256"] for row in actions),
        "experienced field did not transfer into the constraint world",
    )
    require(
        isinstance(fresh, Mapping)
        and fresh.get("status") != "supported"
        and fresh.get("proposed_actions") == [],
        "fresh field unexpectedly possessed the constraint procedure",
    )
    comparison = receipt.get("work_comparison")
    require(
        isinstance(comparison, Mapping)
        and comparison.get("experienced", {}).get(
            "primitive_steps_examined"
        )
        == 3
        and comparison.get("fresh_bounded_search", {}).get(
            "primitive_steps_examined"
        )
        == 6
        and comparison.get("net_saved_steps") == 3,
        "constraint work comparison differs",
    )
    verify_stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--verify-constraint-world"],
        expected=0,
    )
    require(
        json.loads(verify_stdout).get("status") == "PASS",
        "production constraint-world verification failed",
    )
    replay_stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--constraint-world"],
        expected=0,
    )
    require(
        json.loads(replay_stdout).get("status") == "REPLAYED"
        and path.read_bytes() == original,
        "constraint-world replay changed the frozen receipt",
    )
    controls: dict[str, str] = {}
    mutations = {
        "source_mutation": lambda row: row["constraint_source"]["final"].__setitem__(
            0,
            [
                row["constraint_source"]["final"][0][0],
                1 - int(row["constraint_source"]["final"][0][1]),
            ],
        ),
        "witness_mutation": lambda row: row["execution"]["witness"].__setitem__(
            "drive@0",
            1 - int(row["execution"]["witness"]["drive@0"]),
        ),
        "plan_mutation": lambda row: row["experienced_procedure"].__setitem__(
            "proposed_actions",
            list(reversed(row["experienced_procedure"]["proposed_actions"])),
        ),
    }
    for name, mutate in mutations.items():
        try:
            mutated = load_json(path)
            mutate(mutated)
            mutated["content_sha256"] = digest(
                {
                    key: value
                    for key, value in mutated.items()
                    if key != "content_sha256"
                }
            )
            path.write_bytes(canonical(mutated) + b"\n")
            failed_stdout, failed_stderr = run_cli(
                lab,
                ["--data-home", str(home), "--verify-constraint-world"],
                expected=2,
            )
            require(
                any(
                    token in (failed_stdout + failed_stderr).lower()
                    for token in (
                        "constraint source",
                        "constraint execution",
                        "construction plan",
                        "work comparison",
                        "diverged",
                    )
                ),
                f"constraint {name} did not fire",
            )
            controls[name] = "PASS"
        finally:
            path.write_bytes(original)
    require(
        set(controls)
        == {"source_mutation", "witness_mutation", "plan_mutation"},
        "constraint mutation controls are incomplete",
    )
    return {
        "status": "PASS",
        "task_sha256": task["task_sha256"],
        "source_world": task["source_world"],
        "target_world": task["target_world"],
        "experienced_status": experienced["status"],
        "fresh_status": fresh["status"],
        "net_saved_steps": comparison["net_saved_steps"],
        "constraint_status": execution["status"],
        "field_transitions": execution["field_transitions"],
        "witness": witness,
        "independent_models": len(models),
        "replay": "PASS",
        "controls": controls,
    }


def verify_reasoning_world_expansion(
    lab: Path,
    home: Path,
    receipts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild, solve, enumerate, audit, and mutate paired reasoning."""

    stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--reasoning-world"],
        expected=0,
    )
    summary = json.loads(stdout)
    require(
        summary.get("status") in {"PASS", "REPLAYED"},
        "paired-reasoning campaign did not pass or replay",
    )
    path = home / "cross-world" / "paired-reasoning-transfer.json"
    original = path.read_bytes()
    receipt = load_json(path)
    check_sha(receipt, "content_sha256", "paired-reasoning receipt")
    require(
        receipt.get("schema") == REASONING_WORLD_SCHEMA,
        "paired-reasoning receipt schema differs",
    )
    final_generation = receipts[-1]
    selected = final_generation["selected_candidate_id"]
    candidate_root = (
        home
        / "generations"
        / "g0003"
        / "candidates"
        / selected
    )
    files = {
        source.relative_to(candidate_root).as_posix(): source.read_text(
            encoding="utf-8"
        )
        for source in sorted(candidate_root.rglob("*.py"))
        if source.is_file() and "__pycache__" not in source.parts
    }
    parent_digest = workspace_digest(files)
    task = independent_paired_reasoning_task(files, parent_digest)
    require(
        receipt.get("task") == task,
        "paired-reasoning task is not source-derived",
    )
    require(
        task["source_world"] != task["target_world"],
        "paired reasoning did not cross a construction-world boundary",
    )
    reasoning = independent_reasoning_evidence(task)
    require(
        receipt.get("reasoning") == reasoning,
        "paired reasoning differs from independent execution",
    )
    sat_source = task["sources"]["sat_held_out"]
    sat_models = independent_constraint_models(sat_source)
    require(sat_models, "paired SAT source has no model")
    sat_execution = reasoning["held_out"]["sat"]["selected_execution"]
    sat_witness = sat_execution["witness"]
    require(
        isinstance(sat_witness, Mapping),
        "paired SAT execution has no witness",
    )
    sat_audit = independent_constraint_audit(sat_source, sat_witness)
    sat_trace = [
        int(sat_witness[f"drive@{time}"])
        for time in range(int(sat_source["horizon"]))
    ]
    require(
        sat_trace in sat_models,
        "paired SAT witness is absent from independent enumeration",
    )
    unsat_source = task["sources"]["unsat_held_out"]
    unsat_models: list[dict[str, int]] = []
    names = list(unsat_source["inputs"])
    for integer in range(1 << len(names)):
        values = {
            name: (integer >> index) & 1
            for index, name in enumerate(names)
        }
        if all(
            any(values[name] == int(polarity) for name, polarity in clause)
            for clause in unsat_source["clauses"]
        ):
            unsat_models.append(values)
    require(
        unsat_models == [],
        "paired UNSAT source admits an independently enumerated model",
    )
    unsat = reasoning["held_out"]["unsat"]
    require(
        unsat["local_screen"]["status"] == "exhausted"
        and unsat["trained_regime"] == "algebraic"
        and unsat["fresh_regime"] == "conflict"
        and unsat["selected_regime"] == "algebraic",
        "paired field policy did not separate reasoning regimes",
    )
    require(
        unsat["selected_execution"]["status"] == "unsat"
        and unsat["selected_execution"]["certificate"]["kind"] == "hybrid"
        and unsat["selected_execution"]["audit"]["checked"] is True,
        "paired algebraic result lacks an audited UNSAT certificate",
    )
    require(
        unsat["fresh_execution"]["status"] == "unsat"
        and unsat["fresh_execution"]["certificate"]["kind"] == "resolution"
        and unsat["fresh_execution"]["audit"]["checked"] is True,
        "paired fresh-policy control lacks an audited UNSAT certificate",
    )
    from cassi_computation_policy import compile_source
    from verify_hybrid_inference import audit_proof

    compiled_unsat = compile_source(unsat_source)
    direct_hybrid_audit = audit_proof(
        compiled_unsat.clauses,
        unsat["selected_execution"]["certificate"]["proof"],
        variables=compiled_unsat.variables,
    )
    require(
        direct_hybrid_audit.get("status") == "unsat",
        "direct paired hybrid certificate audit failed",
    )
    require(
        reasoning["unsat_field_transition_saving"] == 94
        and unsat["selected_execution"]["field_transitions"] == 1
        and unsat["fresh_execution"]["field_transitions"] == 95,
        "paired reasoning transition comparison differs",
    )
    causal = receipt.get("causal_outcome")
    expected_observed = {
        "sat_held_out": {
            "status": "sat",
            "evidence": "source-checked-witness",
        },
        "unsat_held_out": {
            "status": "unsat",
            "evidence": "independently-audited-certificate",
        },
    }
    require(
        isinstance(causal, Mapping)
        and causal.get("expected") == task["causal_prediction"]
        and causal.get("observed") == expected_observed
        and causal.get("matched") is True,
        "paired reasoning causal outcome differs",
    )
    experienced = receipt.get("experienced_procedure")
    fresh = receipt.get("fresh_field_control")
    required_plan = [
        "locate-binding",
        "compose-operations",
        "compile-successor",
    ]
    actions = (
        experienced.get("proposed_actions")
        if isinstance(experienced, Mapping)
        else None
    )
    require(
        isinstance(experienced, Mapping)
        and experienced.get("status") == "supported"
        and isinstance(actions, list)
        and [row.get("op") for row in actions] == required_plan
        and all(row.get("candidate") == task["task_sha256"] for row in actions),
        "experienced field did not transfer into paired reasoning",
    )
    require(
        isinstance(fresh, Mapping)
        and fresh.get("status") != "supported"
        and fresh.get("proposed_actions") == [],
        "fresh field unexpectedly possessed paired reasoning procedure",
    )
    comparison = receipt.get("construction_work_comparison")
    require(
        isinstance(comparison, Mapping)
        and comparison.get("experienced", {}).get(
            "primitive_steps_examined"
        )
        == 3
        and comparison.get("fresh_bounded_search", {}).get(
            "primitive_steps_examined"
        )
        == 6
        and comparison.get("net_saved_steps") == 3,
        "paired reasoning construction work comparison differs",
    )
    verify_stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--verify-reasoning-world"],
        expected=0,
    )
    require(
        json.loads(verify_stdout).get("status") == "PASS",
        "production paired-reasoning verification failed",
    )
    replay_stdout, _ = run_cli(
        lab,
        ["--data-home", str(home), "--reasoning-world"],
        expected=0,
    )
    require(
        json.loads(replay_stdout).get("status") == "REPLAYED"
        and path.read_bytes() == original,
        "paired-reasoning replay changed the frozen receipt",
    )

    def flip_sat_source(row: dict[str, Any]) -> None:
        final = row["task"]["sources"]["sat_held_out"]["final"]
        final[0][1] = 1 - int(final[0][1])

    def flip_sat_witness(row: dict[str, Any]) -> None:
        witness = row["reasoning"]["held_out"]["sat"][
            "selected_execution"
        ]["witness"]
        witness["drive@0"] = 1 - int(witness["drive@0"])

    def break_unsat_certificate(row: dict[str, Any]) -> None:
        proof = row["reasoning"]["held_out"]["unsat"][
            "selected_execution"
        ]["certificate"]["proof"]
        proof["root_line"] = int(proof["root_line"]) - 1

    def flip_policy_selection(row: dict[str, Any]) -> None:
        row["reasoning"]["held_out"]["unsat"][
            "trained_regime"
        ] = "conflict"

    def reverse_plan(row: dict[str, Any]) -> None:
        procedure = row["experienced_procedure"]
        procedure["proposed_actions"] = list(
            reversed(procedure["proposed_actions"])
        )

    controls: dict[str, str] = {}
    mutations = {
        "source_mutation": flip_sat_source,
        "witness_mutation": flip_sat_witness,
        "certificate_mutation": break_unsat_certificate,
        "policy_mutation": flip_policy_selection,
        "plan_mutation": reverse_plan,
    }
    for name, mutate in mutations.items():
        try:
            mutated = load_json(path)
            mutate(mutated)
            mutated["content_sha256"] = digest(
                {
                    key: value
                    for key, value in mutated.items()
                    if key != "content_sha256"
                }
            )
            path.write_bytes(canonical(mutated) + b"\n")
            failed_stdout, failed_stderr = run_cli(
                lab,
                ["--data-home", str(home), "--verify-reasoning-world"],
                expected=2,
            )
            require(
                any(
                    token in (failed_stdout + failed_stderr).lower()
                    for token in (
                        "paired-reasoning task",
                        "field evidence",
                        "selection",
                        "construction plan",
                        "work comparison",
                        "diverged",
                    )
                ),
                f"paired reasoning {name} did not fire",
            )
            controls[name] = "PASS"
        finally:
            path.write_bytes(original)
    require(
        set(controls)
        == {
            "source_mutation",
            "witness_mutation",
            "certificate_mutation",
            "policy_mutation",
            "plan_mutation",
        },
        "paired reasoning mutation controls are incomplete",
    )
    return {
        "status": "PASS",
        "task_sha256": task["task_sha256"],
        "source_world": task["source_world"],
        "target_world": task["target_world"],
        "experienced_status": experienced["status"],
        "fresh_status": fresh["status"],
        "construction_net_saved_steps": comparison["net_saved_steps"],
        "sat_status": sat_execution["status"],
        "sat_regime": reasoning["held_out"]["sat"]["selected_regime"],
        "sat_independent_models": len(sat_models),
        "sat_final": sat_audit["final"],
        "unsat_status": unsat["selected_execution"]["status"],
        "unsat_regime": unsat["selected_regime"],
        "unsat_fresh_regime": unsat["fresh_regime"],
        "unsat_independent_models": len(unsat_models),
        "unsat_certificate": unsat["selected_execution"]["certificate"][
            "kind"
        ],
        "unsat_fresh_certificate": unsat["fresh_execution"][
            "certificate"
        ]["kind"],
        "unsat_field_transition_saving": reasoning[
            "unsat_field_transition_saving"
        ],
        "replay": "PASS",
        "controls": controls,
    }


def verify_multi_cycle_history_campaign(lab: Path, home: Path) -> dict[str, Any]:
    """Run two explicit continuation cycles and verify replay/mutation controls."""
    for _ in range(2):
        run_cli(lab, ["--data-home", str(home), "--campaign", "--research-cycle"], expected=0)
    receipts = [
        load_json(home / "generations" / f"g000{generation}" / "receipt.json")
        for generation in range(1, 4)
    ]
    trajectory = verify_history_trajectory_receipts(receipts)
    lineage = verify_cumulative_successor_lineage(home, receipts)
    transfer = verify_transfer_learning(home, receipts)
    cross_world = verify_cross_world_expansion(lab, home, receipts)
    constraint_world = verify_constraint_world_expansion(
        lab,
        home,
        receipts,
    )
    reasoning_world = verify_reasoning_world_expansion(
        lab,
        home,
        receipts,
    )
    generation_dir = home / "generations" / "g0003"
    state_path = generation_dir / "state.json"
    pointer_paths = [home / "current.json", home / "promotion.json", generation_dir / "receipt.json", state_path]
    bytes_before = {path: path.read_bytes() for path in pointer_paths}
    generation_names_before = sorted(path.name for path in (home / "generations").glob("g[0-9]*") if path.is_dir())
    replay_stdout, _ = run_cli(lab, ["--data-home", str(home), "--replay"], expected=0)
    replay = json.loads(replay_stdout)
    require(replay.get("status") == "PASS" and replay.get("generation") == 3 and replay.get("state_sha256") == digest(load_json(state_path)), "three-cycle replay did not preserve current state")
    require(all(path.read_bytes() == body for path, body in bytes_before.items()), "three-cycle replay changed persisted bytes")
    restart_stdout, _ = run_cli(lab, ["--data-home", str(home), "--campaign"], expected=0)
    restarted = json.loads(restart_stdout)
    require(restarted.get("status") == "RESTARTED" and restarted.get("generation") == 3, "three-cycle restart created or selected the wrong generation")
    require(sorted(path.name for path in (home / "generations").glob("g[0-9]*") if path.is_dir()) == generation_names_before, "three-cycle restart changed generation set")
    require(all(path.read_bytes() == body for path, body in bytes_before.items()), "three-cycle restart changed persisted bytes")
    state_original = state_path.read_bytes()
    try:
        mutated_state = load_json(state_path)
        mutated_state["field_question_id"] = "three-cycle-mutation-control"
        state_path.write_bytes(canonical(mutated_state) + b"\\n")
        stdout, stderr = run_cli(lab, ["--data-home", str(home), "--replay"], expected=2)
        require(any(token in (stdout + stderr).lower() for token in ("state", "pointer", "mismatch", "mutation", "digest")), "three-cycle state mutation was accepted")
    finally:
        state_path.write_bytes(state_original)
    selected_candidate = receipts[-1]["selected_candidate_id"]
    source_path = generation_dir / "candidates" / selected_candidate / "src" / "core_math.py"
    source_original = source_path.read_bytes()
    try:
        source_path.write_bytes(source_original + b"\\n# three-cycle mutation-control\\n")
        stdout, stderr = run_cli(lab, ["--data-home", str(home), "--replay"], expected=2)
        require(any(token in (stdout + stderr).lower() for token in ("candidate replay", "source", "digest", "diverged", "mismatch")), "three-cycle source mutation was accepted")
    finally:
        source_path.write_bytes(source_original)
    field_home = home / "field"
    field_files = [path for path in sorted(field_home.rglob("*")) if path.is_file() and path.name != "OWNER.lock"]
    require(field_files, "three-cycle field mutation control found no persisted field bytes")
    field_target = next((path for path in field_files if path.name in {"CURRENT", "REVOCATION"} or "manifest" in path.name.lower() or "checkpoint" in path.name.lower()), field_files[0])
    field_original = field_target.read_bytes()
    try:
        field_target.write_bytes(field_original + b"\\x00three-cycle-mutation-control")
        try:
            field_state_receipt(field_home)
        except Exception as exc:
            require(any(token in str(exc).lower() for token in ("corrupt", "digest", "checkpoint", "invalid", "quarantine", "decode")), "three-cycle field mutation rejection lacked integrity evidence")
        else:
            raise AssertionError("three-cycle persisted field mutation was accepted")
    finally:
        field_target.write_bytes(field_original)
    recovered_stdout, _ = run_cli(lab, ["--data-home", str(home), "--replay"], expected=0)
    recovered = json.loads(recovered_stdout)
    require(recovered.get("status") == "PASS" and recovered.get("generation") == 3, "three-cycle replay did not recover after mutation controls")
    return {
        "status": "PASS",
        "trajectory": trajectory,
        "lineage": lineage,
        "transfer_learning": transfer,
        "cross_world": cross_world,
        "constraint_world": constraint_world,
        "reasoning_world": reasoning_world,
        "replay": "PASS",
        "restart": "PASS",
        "state_mutation": "PASS",
        "source_mutation": "PASS",
        "field_mutation": "PASS",
    }


def mutate_and_require_controls(lab: Path, home: Path, receipt: Mapping[str, Any]) -> dict[str, str]:
    controls: dict[str, str] = {}
    field_home = home / "field"
    field_files = [path for path in sorted(field_home.rglob("*")) if path.is_file() and path.name not in {"OWNER.lock"}]
    require(field_files, "no persisted field bytes available for mutation control")
    target = next((path for path in field_files if path.name in {"CURRENT", "REVOCATION"} or "manifest" in path.name.lower() or "checkpoint" in path.name.lower()), field_files[0])
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\x00mutation-control")
        try:
            field_state_receipt(field_home)
        except Exception as exc:
            controls["persisted_field_mutation"] = "PASS"
            require(any(token in str(exc).lower() for token in ("corrupt", "digest", "checkpoint", "invalid", "quarantine", "decode")), "persisted field mutation rejection lacked integrity evidence")
        else:
            raise AssertionError("persisted field mutation was accepted")
    finally:
        target.write_bytes(original)
    state_path = home / "generations" / "g0001" / "state.json"
    original_state = state_path.read_bytes()
    state = load_json(state_path)
    try:
        state["field_question_id"] = "mutation-control-question"
        state_path.write_bytes(canonical(state) + b"\n")
        stdout, stderr = run_cli(lab, ["--data-home", str(home), "--replay"], expected=2)
        require(any(token in (stdout + stderr).lower() for token in ("state", "pointer", "mismatch", "mutation", "digest")), "generation state mutation rejection lacked integrity evidence")
        controls["generation_mutation"] = "PASS"
    finally:
        state_path.write_bytes(original_state)
    source_path = home / "generations" / "g0001" / "candidates" / receipt["selected_candidate_id"] / "src" / "core_math.py"
    original_source = source_path.read_bytes()
    try:
        source_path.write_bytes(original_source + b"\n# mutation-control\n")
        stdout, stderr = run_cli(lab, ["--data-home", str(home), "--replay"], expected=2)
        require(any(token in (stdout + stderr).lower() for token in ("candidate replay", "source", "digest", "diverged", "mismatch")), "source mutation rejection lacked replay evidence")
        controls["source_mutation"] = "PASS"
    finally:
        source_path.write_bytes(original_source)
    receipt_path = home / "generations" / "g0001" / "receipt.json"
    original_receipt = receipt_path.read_bytes()
    try:
        mutated = load_json(receipt_path)
        mutated["selected_candidate_id"] = next(row["candidate_id"] for row in mutated["candidates"] if row["candidate_id"] != receipt["selected_candidate_id"])
        mutated["content_sha256"] = digest(stable_receipt(mutated))
        receipt_path.write_bytes(canonical(mutated) + b"\n")
        stdout, stderr = run_cli(lab, ["--data-home", str(home), "--verify-receipt", str(receipt_path)], expected=0)
        require(json.loads(stdout).get("status") == "PASS", "recomputed semantic receipt mutation was not accepted by production digest verifier")
        try:
            verify_receipt_semantics(mutated, workspace_digest(parent_workspace()))
        except AssertionError:
            controls["receipt_semantic_mutation"] = "PASS"
        else:
            raise AssertionError("independent receipt semantic mutation control did not fire")
    finally:
        receipt_path.write_bytes(original_receipt)
    stale = load_json(receipt_path)
    try:
        stale["content_sha256"] = "0" * 64
        receipt_path.write_bytes(canonical(stale) + b"\n")
        stdout, stderr = run_cli(lab, ["--data-home", str(home), "--verify-receipt", str(receipt_path)], expected=2)
        require("content_sha256 mismatch" in (stdout + stderr), "stale receipt digest control did not fire")
        controls["receipt_digest_mutation"] = "PASS"
    finally:
        receipt_path.write_bytes(original_receipt)
    require(set(controls) == {"persisted_field_mutation", "generation_mutation", "source_mutation", "receipt_semantic_mutation", "receipt_digest_mutation"}, "mutation controls incomplete")
    return controls


def verify(lab: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cassimindfield-redesign-verify-") as temporary:
        home = Path(temporary) / "campaign"
        run_cli(lab, ["--data-home", str(home), "--campaign"], expected=0)
        current = load_json(home / "current.json")
        require(current.get("generation") == 1, "campaign did not produce generation 1")
        generation_dir = home / "generations" / "g0001"
        receipt = load_json(generation_dir / "receipt.json")
        parent = load_json(home / "generations" / "g0000" / "receipt.json")
        parent_files = parent_workspace()
        parent_digest = workspace_digest(parent_files)
        require(parent.get("content_sha256") == digest(stable_receipt(parent)), "parent receipt digest mismatch")
        require(receipt.get("parent_receipt_sha256") == parent.get("content_sha256"), "receipt parent digest mismatch")
        verify_receipt_semantics(receipt, parent_digest)
        question = receipt["field_question"]
        selection = receipt["field_selection"]
        verify_candidate_rows(receipt, parent_files, parent_digest, generation_dir)
        verify_agendas_and_field(receipt, home, parent_digest)
        state_path = generation_dir / "state.json"
        state = load_json(state_path)
        assert_state_semantics(receipt, state, parent_digest)
        check_sha(current, "pointer_sha256", "current pointer")
        require(current.get("receipt_sha256") == receipt.get("content_sha256") and current.get("state_sha256") == digest(state), "current pointer does not reference receipt/state")
        promotion = load_json(home / "promotion.json")
        check_sha(promotion, "pointer_sha256", "promotion pointer")
        require(promotion.get("generation") == 1 and promotion.get("receipt_sha256") == receipt.get("content_sha256") and promotion.get("candidate_id") == receipt.get("selected_candidate_id"), "promotion pointer differs")
        field_state = field_state_receipt(home / "field")
        require(field_state.get("state_sha256") == selection.get("field_state_out_sha256") and field_state.get("regional_state_sha256") == selection.get("field_state_out_sha256"), "reopened field hash differs from selection")
        generation_names_before = sorted(path.name for path in (home / "generations").glob("g[0-9]*") if path.is_dir())
        pointer_bytes_before = (home / "current.json").read_bytes()
        promotion_bytes_before = (home / "promotion.json").read_bytes()
        receipt_bytes_before = (generation_dir / "receipt.json").read_bytes()
        replay = json.loads(run_cli(lab, ["--data-home", str(home), "--replay"], expected=0)[0])
        require(replay.get("status") == "PASS" and replay.get("state_sha256") == digest(state), "replay did not preserve redesign state")
        restarted = json.loads(run_cli(lab, ["--data-home", str(home), "--campaign"], expected=0)[0])
        require(restarted.get("status") == "RESTARTED" and restarted.get("generation") == 1, "restart did not preserve generation")
        require(sorted(path.name for path in (home / "generations").glob("g[0-9]*") if path.is_dir()) == generation_names_before, "restart created a new generation")
        require((home / "current.json").read_bytes() == pointer_bytes_before and (home / "promotion.json").read_bytes() == promotion_bytes_before and (generation_dir / "receipt.json").read_bytes() == receipt_bytes_before, "replay/restart changed persisted pointers or receipt")
        reopened_after = field_state_receipt(home / "field")
        require(reopened_after.get("state_sha256") == field_state.get("state_sha256") and reopened_after.get("regional_state_sha256") == field_state.get("regional_state_sha256"), "reopen changed field hashes")
        controls = mutate_and_require_controls(lab, home, receipt)
        trajectory_controls = verify_multi_cycle_history_campaign(lab, home)
        direct_facade = verify_direct_facade_campaign(lab, parent_digest)
        result = {
            "status": "PASS",
            "schema": RECEIPT_SCHEMA,
            "generation": 1,
            "selected_candidate_id": receipt["selected_candidate_id"],
            "selected_question_id": question["question_id"],
            "selected_question_compiler_family": question["compiler_family"],
            "question_option_count": len(question["question_options"]),
            "selected_candidate_agenda_rank": selection.get("candidate_agenda_rank", selection.get("selected_candidate_rank")),
            "selected_question_agenda_rank": question["selected_question_agenda_rank"],
            "field_state_sha256": receipt["field_state_sha256"],
            "field_question_origin": "PASS",
            "bounded_compiler_catalog": "PASS",
            "resident_question_query": "PASS",
            "field_selection": "PASS",
            "autonomous_agenda": "PASS",
            "fresh_field_lesion": "PASS",
            "reopen_state": "PASS",
            "replay": "PASS",
            "persisted_field_mutation": controls["persisted_field_mutation"],
            "generation_mutation": controls["generation_mutation"],
            "source_mutation": controls["source_mutation"],
            "receipt_semantic_mutation": controls["receipt_semantic_mutation"],
            "receipt_digest_mutation": controls["receipt_digest_mutation"],
            "multi_cycle_history": trajectory_controls["status"],
            "multi_cycle_families": trajectory_controls["trajectory"]["families"],
            "cumulative_lineage": trajectory_controls["lineage"]["status"],
            "cumulative_file_counts": trajectory_controls["lineage"]["file_counts"],
            "transfer_learning": trajectory_controls["transfer_learning"]["status"],
            "transfer_net_saved_steps": trajectory_controls["transfer_learning"][
                "net_saved_steps"
            ],
            "unfamiliar_successor_applications": trajectory_controls[
                "transfer_learning"
            ]["unfamiliar_successor_applications"],
            "experienced_procedure_status": trajectory_controls[
                "transfer_learning"
            ]["experienced_status"],
            "fresh_procedure_status": trajectory_controls["transfer_learning"][
                "fresh_status"
            ],
            "multi_cycle_replay": trajectory_controls["replay"],
            "multi_cycle_restart": trajectory_controls["restart"],
            "multi_cycle_state_mutation": trajectory_controls["state_mutation"],
            "multi_cycle_source_mutation": trajectory_controls["source_mutation"],
            "multi_cycle_field_mutation": trajectory_controls["field_mutation"],
            "cross_world_transfer": trajectory_controls["cross_world"]["status"],
            "cross_world_source": trajectory_controls["cross_world"][
                "source_world"
            ],
            "cross_world_target": trajectory_controls["cross_world"][
                "target_world"
            ],
            "cross_world_net_saved_steps": trajectory_controls["cross_world"][
                "net_saved_steps"
            ],
            "cross_world_experienced_status": trajectory_controls[
                "cross_world"
            ]["experienced_status"],
            "cross_world_fresh_status": trajectory_controls["cross_world"][
                "fresh_status"
            ],
            "cross_world_execution": trajectory_controls["cross_world"][
                "execution"
            ],
            "cross_world_replay": trajectory_controls["cross_world"]["replay"],
            "cross_world_source_mutation": trajectory_controls["cross_world"][
                "controls"
            ]["source_mutation"],
            "cross_world_plan_mutation": trajectory_controls["cross_world"][
                "controls"
            ]["plan_mutation"],
            "constraint_world_transfer": trajectory_controls[
                "constraint_world"
            ]["status"],
            "constraint_world_source": trajectory_controls[
                "constraint_world"
            ]["source_world"],
            "constraint_world_target": trajectory_controls[
                "constraint_world"
            ]["target_world"],
            "constraint_world_net_saved_steps": trajectory_controls[
                "constraint_world"
            ]["net_saved_steps"],
            "constraint_world_experienced_status": trajectory_controls[
                "constraint_world"
            ]["experienced_status"],
            "constraint_world_fresh_status": trajectory_controls[
                "constraint_world"
            ]["fresh_status"],
            "constraint_world_status": trajectory_controls[
                "constraint_world"
            ]["constraint_status"],
            "constraint_world_field_transitions": trajectory_controls[
                "constraint_world"
            ]["field_transitions"],
            "constraint_world_witness": trajectory_controls[
                "constraint_world"
            ]["witness"],
            "constraint_world_independent_models": trajectory_controls[
                "constraint_world"
            ]["independent_models"],
            "constraint_world_replay": trajectory_controls[
                "constraint_world"
            ]["replay"],
            "constraint_world_source_mutation": trajectory_controls[
                "constraint_world"
            ]["controls"]["source_mutation"],
            "constraint_world_witness_mutation": trajectory_controls[
                "constraint_world"
            ]["controls"]["witness_mutation"],
            "constraint_world_plan_mutation": trajectory_controls[
                "constraint_world"
            ]["controls"]["plan_mutation"],
            "reasoning_world_transfer": trajectory_controls[
                "reasoning_world"
            ]["status"],
            "reasoning_world_source": trajectory_controls[
                "reasoning_world"
            ]["source_world"],
            "reasoning_world_target": trajectory_controls[
                "reasoning_world"
            ]["target_world"],
            "reasoning_world_experienced_status": trajectory_controls[
                "reasoning_world"
            ]["experienced_status"],
            "reasoning_world_fresh_status": trajectory_controls[
                "reasoning_world"
            ]["fresh_status"],
            "reasoning_world_construction_net_saved_steps": trajectory_controls[
                "reasoning_world"
            ]["construction_net_saved_steps"],
            "reasoning_world_sat_status": trajectory_controls[
                "reasoning_world"
            ]["sat_status"],
            "reasoning_world_sat_regime": trajectory_controls[
                "reasoning_world"
            ]["sat_regime"],
            "reasoning_world_sat_independent_models": trajectory_controls[
                "reasoning_world"
            ]["sat_independent_models"],
            "reasoning_world_unsat_status": trajectory_controls[
                "reasoning_world"
            ]["unsat_status"],
            "reasoning_world_unsat_regime": trajectory_controls[
                "reasoning_world"
            ]["unsat_regime"],
            "reasoning_world_unsat_fresh_regime": trajectory_controls[
                "reasoning_world"
            ]["unsat_fresh_regime"],
            "reasoning_world_unsat_independent_models": trajectory_controls[
                "reasoning_world"
            ]["unsat_independent_models"],
            "reasoning_world_unsat_certificate": trajectory_controls[
                "reasoning_world"
            ]["unsat_certificate"],
            "reasoning_world_unsat_fresh_certificate": trajectory_controls[
                "reasoning_world"
            ]["unsat_fresh_certificate"],
            "reasoning_world_unsat_field_transition_saving": trajectory_controls[
                "reasoning_world"
            ]["unsat_field_transition_saving"],
            "reasoning_world_replay": trajectory_controls[
                "reasoning_world"
            ]["replay"],
            "reasoning_world_source_mutation": trajectory_controls[
                "reasoning_world"
            ]["controls"]["source_mutation"],
            "reasoning_world_witness_mutation": trajectory_controls[
                "reasoning_world"
            ]["controls"]["witness_mutation"],
            "reasoning_world_certificate_mutation": trajectory_controls[
                "reasoning_world"
            ]["controls"]["certificate_mutation"],
            "reasoning_world_policy_mutation": trajectory_controls[
                "reasoning_world"
            ]["controls"]["policy_mutation"],
            "reasoning_world_plan_mutation": trajectory_controls[
                "reasoning_world"
            ]["controls"]["plan_mutation"],
            "direct_facade_campaign": direct_facade["status"],
            "direct_facade_selected_candidate_id": direct_facade["selected_candidate_id"],
            "direct_facade_selected_question_id": direct_facade["selected_question_id"],
            "model_call_observability": "NOT_EXPOSED",
        }
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab", default=str(MIND_FIELD / "redesign_lab.py"))
    args = parser.parse_args()
    try:
        print(json.dumps(verify(Path(args.lab).resolve()), sort_keys=True))
        return 0
    except (AssertionError, OSError, RuntimeError, ValueError, json.JSONDecodeError, ImportError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
