"""Field-guided, bounded CassiPy program synthesis.

This module is the first open-vocabulary algorithm-distiller surface.  It does
not contain a hidden strategy catalog or a learned ranker.  Fixed grammar
operators generate a small typed candidate frontier; the supplied field may
order and learn from those candidates.  All executable behavior remains in the
bounded CassiPy interpreter.
"""

from __future__ import annotations

import hashlib
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

_CASSIQWEN_ROOT = Path(__file__).resolve().parents[1] / "CassiQwen" / "research"
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))

from cassi_market_contracts import Program, Skill, canonical_bytes, digest_value
from cassi_python import execute_program, parse_source


SYNTHESIS_SCHEMA = "cassi.market-program-synthesis.v1"
NUMERIC_TYPES = (int, float)


class SynthesisError(ValueError):
    """A synthesis request or candidate violates the bounded contract."""


class FieldGuidance(Protocol):
    """Minimal field interface needed by the synthesizer."""

    def predict(self, signature: str, mutation: str) -> Mapping[str, Any]:
        ...

    def learn(self, signature: str, mutation: str, outcome: str) -> None:
        ...


@dataclass(frozen=True, slots=True)
class SynthesisBudget:
    max_candidates: int = 32
    max_source_chars: int = 8192
    max_ast_nodes: int = 512
    max_steps: int = 10_000
    max_call_depth: int = 32

    def __post_init__(self) -> None:
        for name in ("max_candidates", "max_source_chars", "max_ast_nodes", "max_steps", "max_call_depth"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SynthesisError(f"{name} must be a positive integer")

    def as_dict(self) -> dict[str, int]:
        return {
            "max_candidates": self.max_candidates,
            "max_source_chars": self.max_source_chars,
            "max_ast_nodes": self.max_ast_nodes,
            "max_steps": self.max_steps,
            "max_call_depth": self.max_call_depth,
        }


@dataclass(frozen=True, slots=True)
class GrammarOperator:
    """One fixed, typed transformation over a numeric CassiPy result."""

    name: str
    parameter_names: tuple[str, ...]
    defaults: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("-", "").isalnum():
            raise SynthesisError("grammar operator name must be identifier-like")
        if len(self.parameter_names) != len(self.defaults):
            raise SynthesisError("grammar operator parameters and defaults differ")
        for name, default in zip(self.parameter_names, self.defaults):
            if not name or not name.isidentifier() or not name.startswith("synth_"):
                raise SynthesisError("synthesized parameters must use the synth_ namespace")
            if isinstance(default, bool) or not isinstance(default, NUMERIC_TYPES) or not math.isfinite(float(default)):
                raise SynthesisError("grammar defaults must be finite numbers")

    def suffix(self) -> str:
        if self.name == "identity":
            return ""
        if self.name == "offset":
            return "\nresult = result + synth_offset"
        if self.name == "scale":
            return "\nresult = result * synth_scale"
        if self.name == "clip":
            return (
                "\nif result > synth_upper:\n"
                "    result = synth_upper\n"
                "if result < synth_lower:\n"
                "    result = synth_lower"
            )
        raise SynthesisError(f"unknown grammar operator: {self.name}")

    def transform_expected(self, value: Any) -> Any:
        if self.name == "identity":
            return value
        if isinstance(value, bool) or not isinstance(value, NUMERIC_TYPES):
            raise SynthesisError("numeric grammar requires numeric expected outputs")
        if self.name == "offset":
            return value + self.defaults[0]
        if self.name == "scale":
            return value * self.defaults[0]
        if self.name == "clip":
            return min(self.defaults[0], max(self.defaults[1], value))
        raise SynthesisError(f"unknown grammar operator: {self.name}")


DEFAULT_OPERATORS = (
    GrammarOperator("identity", (), ()),
    GrammarOperator("offset", ("synth_offset",), (1.0,)),
    GrammarOperator("scale", ("synth_scale",), (2.0,)),
    GrammarOperator("clip", ("synth_upper", "synth_lower"), (1.0, -1.0)),
)


def _node_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return 1 + sum(_node_count(key) + _node_count(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return 1 + sum(_node_count(item) for item in value)
    return 1


def _skill_cases(skill: Skill) -> tuple[Mapping[str, Any], ...]:
    cases = skill.verification_cases
    if not cases:
        raise SynthesisError(f"skill {skill.skill_id} has no verification cases")
    for case in cases:
        if not isinstance(case, Mapping) or "expected" not in case:
            raise SynthesisError(f"skill {skill.skill_id} has no expected output")
        if not isinstance(case.get("inputs"), Mapping):
            raise SynthesisError(f"skill {skill.skill_id} has malformed case inputs")
    return cases


def _numeric_cases(skill: Skill) -> tuple[Mapping[str, Any], ...]:
    cases = _skill_cases(skill)
    for case in cases:
        expected = case["expected"]
        if isinstance(expected, bool) or not isinstance(expected, NUMERIC_TYPES):
            raise SynthesisError(f"skill {skill.skill_id} is not numeric and cannot use numeric grammar")
    return cases


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, NUMERIC_TYPES):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, (list, tuple)):
        return "list"
    if isinstance(value, Mapping):
        return "record"
    return "runtime-value"


def _skill_output_type(skill: Skill) -> str:
    return _value_type(_skill_cases(skill)[0]["expected"])


def _skill_parameters(skill: Skill) -> tuple[str, ...]:
    parameters = skill.input_schema.get("parameters")
    if not isinstance(parameters, list) or any(not isinstance(value, str) for value in parameters):
        raise SynthesisError(f"skill {skill.skill_id} input schema has no parameter contract")
    return tuple(parameters)


def _candidate_id(source: str, skill_id: str, operator: str) -> str:
    digest = hashlib.sha256(canonical_bytes({"skill_id": skill_id, "operator": operator, "source": source})).hexdigest()
    return f"synth-{digest[:20]}"


def _field_preference(prediction: Mapping[str, Any]) -> tuple[int, float]:
    outcome = prediction.get("outcome")
    priority = {
        "promote": 0,
        "supported": 0,
        "uncertain": 1,
        None: 1,
        "reject": 2,
        "contradicted": 2,
    }.get(outcome, 1)
    score = prediction.get("score")
    numeric_score = float(score) if isinstance(score, NUMERIC_TYPES) and not isinstance(score, bool) else 0.0
    return priority, -numeric_score


@dataclass(frozen=True, slots=True)
class Candidate:
    program: Program
    skill_id: str
    mutation: str
    field_prediction: Mapping[str, Any]
    verification: tuple[Mapping[str, Any], ...]
    outcome: str = "unassessed"

    @property
    def objective(self) -> float:
        passed = sum(1 for row in self.verification if row.get("passed"))
        return passed / len(self.verification) if self.verification else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.program.program_id,
            "skill_id": self.skill_id,
            "mutation": self.mutation,
            "program": self.program.as_dict(),
            "program_sha256": self.program.content_sha256,
            "field_prediction": dict(self.field_prediction),
            "verification": [dict(row) for row in self.verification],
            "objective": self.objective,
            "outcome": self.outcome,
        }


class CandidateFrontier:
    """Deterministic candidate store; adaptive preference stays in the field."""

    def __init__(self, *, task_id: str, budget: SynthesisBudget) -> None:
        if not task_id or not isinstance(task_id, str):
            raise SynthesisError("task_id must be nonempty text")
        self.task_id = task_id
        self.budget = budget
        self._candidates: dict[str, Candidate] = {}

    def add(self, candidate: Candidate) -> None:
        if len(self._candidates) >= self.budget.max_candidates and candidate.program.program_id not in self._candidates:
            raise SynthesisError("candidate frontier budget exhausted")
        prior = self._candidates.get(candidate.program.program_id)
        if prior is not None and prior.program.content_sha256 != candidate.program.content_sha256:
            raise SynthesisError("candidate identity collision")
        self._candidates[candidate.program.program_id] = candidate

    def candidates(self) -> tuple[Candidate, ...]:
        return tuple(self._candidates.values())

    def best(self) -> Candidate:
        if not self._candidates:
            raise SynthesisError("candidate frontier is empty")
        return max(
            self._candidates.values(),
            key=lambda candidate: (
                candidate.objective,
                -_field_preference(candidate.field_prediction)[0],
                -_field_preference(candidate.field_prediction)[1],
                -len(candidate.program.source),
                candidate.program.program_id,
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "budget": self.budget.as_dict(),
            "candidate_count": len(self._candidates),
            "candidates": [candidate.as_dict() for candidate in self.candidates()],
        }


class ProgramSynthesizer:
    """Generate, execute, and assess a bounded typed candidate frontier."""

    def __init__(
        self,
        *,
        budget: SynthesisBudget | None = None,
        operators: Sequence[GrammarOperator] = DEFAULT_OPERATORS,
    ) -> None:
        self.budget = budget or SynthesisBudget()
        self.operators = tuple(operators)
        if not self.operators:
            raise SynthesisError("at least one grammar operator is required")
        names = [operator.name for operator in self.operators]
        if len(set(names)) != len(names):
            raise SynthesisError("grammar operator names must be unique")

    def _program_for(
        self,
        skill: Skill,
        operator: GrammarOperator,
        evidence_roots: tuple[str, ...],
    ) -> Program:
        base_parameters = _skill_parameters(skill)
        parameters = base_parameters + operator.parameter_names
        source = skill.source_program + operator.suffix()
        if len(source) > self.budget.max_source_chars:
            raise SynthesisError(f"candidate {skill.skill_id}/{operator.name} exceeds source budget")
        try:
            ast = parse_source(source, params=parameters)
        except Exception as exc:
            raise SynthesisError(f"candidate {skill.skill_id}/{operator.name} is not valid CassiPy") from exc
        nodes = _node_count(ast)
        if nodes > self.budget.max_ast_nodes:
            raise SynthesisError(f"candidate {skill.skill_id}/{operator.name} exceeds AST budget")
        return Program(
            program_id=_candidate_id(source, skill.skill_id, operator.name),
            parent_ids=(skill.skill_id,),
            source=source,
            canonical_ast=ast,
            typed_inputs={
                "parameters": list(parameters),
                "base_skill": skill.skill_id,
                "base_result_type": _skill_output_type(skill),
            },
            typed_outputs={
                "type": _skill_output_type(skill) if operator.name == "identity" else "number",
            },
            guards=("cassi-python-v1", "numeric-inputs" if operator.name != "identity" else "typed-result"),
            state_ports={},
            resource_budget={
                "max_source_chars": self.budget.max_source_chars,
                "max_ast_nodes": self.budget.max_ast_nodes,
                "ast_nodes": nodes,
                "max_steps": self.budget.max_steps,
                "max_call_depth": self.budget.max_call_depth,
            },
            evidence_roots=evidence_roots,
            skill_dependencies=(skill.skill_id,),
        )

    def _evaluate(
        self,
        skill: Skill,
        operator: GrammarOperator,
        program: Program,
    ) -> tuple[Mapping[str, Any], ...]:
        rows: list[Mapping[str, Any]] = []
        cases = _skill_cases(skill)
        if operator.name != "identity":
            _numeric_cases(skill)
        for case in cases:
            inputs = dict(case["inputs"])
            inputs.update(dict(zip(operator.parameter_names, operator.defaults)))
            expected = operator.transform_expected(case["expected"])
            try:
                result = execute_program(
                    program.canonical_ast,
                    inputs,
                    max_steps=self.budget.max_steps,
                    max_call_depth=self.budget.max_call_depth,
                )
                passed = result.value == expected
                rows.append(
                    {
                        "case_id": str(case["case_id"]),
                        "inputs": inputs,
                        "expected": expected,
                        "actual": result.value,
                        "steps": result.steps,
                        "passed": passed,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "case_id": str(case["case_id"]),
                        "inputs": inputs,
                        "expected": expected,
                        "actual": None,
                        "steps": None,
                        "passed": False,
                        "error": type(exc).__name__,
                    }
                )
        return tuple(rows)

    @staticmethod
    def _field_prediction(field: FieldGuidance | None, signature: str, mutation: str) -> Mapping[str, Any]:
        if field is None:
            return {"status": "unavailable", "outcome": None}
        prediction = field.predict(signature, mutation)
        if not isinstance(prediction, Mapping):
            raise SynthesisError("field prediction must be an object")
        return dict(prediction)

    def synthesize(
        self,
        skills: Sequence[Skill],
        *,
        task_id: str,
        evidence_roots: Sequence[str] = (),
        field: FieldGuidance | None = None,
        learn_field: bool = False,
    ) -> dict[str, Any]:
        """Create a candidate frontier and assess it before any field update."""
        if not skills:
            raise SynthesisError("synthesis requires at least one skill")
        roots = tuple(str(root) for root in evidence_roots)
        frontier = CandidateFrontier(task_id=task_id, budget=self.budget)
        generated: list[Candidate] = []
        for skill in skills:
            cases = _skill_cases(skill)
            numeric_output = all(
                not isinstance(case["expected"], bool) and isinstance(case["expected"], NUMERIC_TYPES)
                for case in cases
            )
            usable_operators = tuple(
                operator for operator in self.operators if operator.name == "identity" or numeric_output
            )
            signature = f"program-synthesis:{task_id}:{skill.skill_id}"
            ordered_operators = [
                (
                    operator,
                    self._field_prediction(field, signature, f"{skill.skill_id}/{operator.name}"),
                )
                for operator in usable_operators
            ]
            ordered_operators.sort(key=lambda row: (_field_preference(row[1]), row[0].name))
            for operator, prediction in ordered_operators:
                if len(generated) >= self.budget.max_candidates:
                    break
                mutation = f"{skill.skill_id}/{operator.name}"
                try:
                    program = self._program_for(skill, operator, roots + skill.support_roots)
                    verification = self._evaluate(skill, operator, program)
                    passed = all(bool(row.get("passed")) for row in verification)
                    outcome = "supported" if passed else "contradicted"
                except SynthesisError as exc:
                    if learn_field:
                        raise
                    continue
                candidate = Candidate(
                    program=program,
                    skill_id=skill.skill_id,
                    mutation=mutation,
                    field_prediction=prediction,
                    verification=verification,
                    outcome=outcome,
                )
                frontier.add(candidate)
                generated.append(candidate)
                if learn_field and field is not None:
                    field.learn(signature, mutation, outcome)
            if len(generated) >= self.budget.max_candidates:
                break
        if not generated:
            raise SynthesisError("grammar produced no executable candidates")
        selected = frontier.best()
        return {
            "schema": SYNTHESIS_SCHEMA,
            "task_id": task_id,
            "budget": self.budget.as_dict(),
            "field_learning": learn_field,
            "frontier": frontier.as_dict(),
            "selected": selected.as_dict(),
            "frontier_sha256": digest_value(frontier.as_dict()),
        }


__all__ = [
    "Candidate",
    "CandidateFrontier",
    "DEFAULT_OPERATORS",
    "FieldGuidance",
    "GrammarOperator",
    "NUMERIC_TYPES",
    "ProgramSynthesizer",
    "SynthesisBudget",
    "SYNTHESIS_SCHEMA",
    "SynthesisError",
]
