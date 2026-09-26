"""Export and verify the learned, executable CassiPy capability layer.

The trading field stores market-specific outcomes.  This module keeps that
state separate from the already verified math/Python capability substrate:
canonical CassiPy programs, their ASTs, input contracts, and differential
checks against restricted CPython.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_CASSIQWEN_ROOT = Path(__file__).resolve().parents[1] / "CassiQwen" / "research"
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))

from cassi_market_contracts import ContractError, Skill  # noqa: E402
from cassi_python import (  # noqa: E402
    FULL_CURRICULUM,
    PROGRAM_SCHEMA,
    PythonCase,
    PythonLesson,
    content_digest_matches,
    digest_value,
    parse_source,
    verify_differential,
)

SKILL_BUNDLE_SCHEMA = "cassi.skill-bundle.v1"


class SkillBundleError(RuntimeError):
    """A skill bundle failed its executable or provenance contract."""


def _case_document(lesson: PythonLesson) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in lesson.cases:
        row: dict[str, Any] = {"case_id": case.case_id, "inputs": dict(case.inputs)}
        if case.expected is not None:
            row["expected"] = case.expected
        rows.append(row)
    return rows


def _skill_document(lesson: PythonLesson) -> dict[str, Any]:
    cases = _case_document(lesson)
    parameters = list(lesson.cases[0].inputs) if lesson.cases else []
    program = parse_source(lesson.source, params=parameters)
    differential = verify_differential(lesson.source, lesson.cases)
    if not differential["passed"]:
        raise SkillBundleError(f"curriculum skill {lesson.lesson_id} failed differential verification")
    return {
        "skill_id": lesson.lesson_id,
        "title": lesson.title,
        "domains": list(lesson.domains),
        "source": lesson.source,
        "parameters": parameters,
        "program": program,
        "program_sha256": digest_value(program),
        "cases": cases,
        "cases_sha256": digest_value(cases),
        "differential": differential,
    }


def build_skill_bundle(lessons: Sequence[PythonLesson] = FULL_CURRICULUM) -> dict[str, Any]:
    """Build a portable bundle from the verified CassiPy curriculum."""
    if not lessons:
        raise SkillBundleError("skill bundle cannot be empty")
    skills = [_skill_document(lesson) for lesson in lessons]
    body: dict[str, Any] = {
        "schema": SKILL_BUNDLE_SCHEMA,
        "program_schema": PROGRAM_SCHEMA,
        "source": "CassiQwen/research/cassi_python.py:FULL_CURRICULUM",
        "skill_count": len(skills),
        "skills": skills,
    }
    body["content_sha256"] = digest_value(body)
    return body


def verify_skill_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if bundle.get("schema") != SKILL_BUNDLE_SCHEMA:
        raise SkillBundleError("skill bundle schema mismatch")
    if bundle.get("program_schema") != PROGRAM_SCHEMA:
        raise SkillBundleError("skill bundle program schema mismatch")
    skills = bundle.get("skills")
    if not isinstance(skills, list) or not skills:
        raise SkillBundleError("skill bundle has no skills")
    if bundle.get("skill_count") != len(skills):
        raise SkillBundleError("skill count mismatch")
    for skill in skills:
        if not isinstance(skill, Mapping):
            raise SkillBundleError("skill row is not an object")
        source = skill.get("source")
        parameters = skill.get("parameters")
        if not isinstance(source, str) or not isinstance(parameters, list):
            raise SkillBundleError("skill source contract is malformed")
        program = parse_source(source, params=tuple(parameters))
        if digest_value(program) != skill.get("program_sha256"):
            raise SkillBundleError(f"skill {skill.get('skill_id')} program digest mismatch")
        cases = skill.get("cases")
        if not isinstance(cases, list) or digest_value(cases) != skill.get("cases_sha256"):
            raise SkillBundleError(f"skill {skill.get('skill_id')} case digest mismatch")
        python_cases: list[PythonCase] = []
        for case in cases:
            if not isinstance(case, Mapping) or not isinstance(case.get("inputs"), Mapping):
                raise SkillBundleError(f"skill {skill.get('skill_id')} case is malformed")
            if "expected" in case:
                python_cases.append(PythonCase(str(case["case_id"]), dict(case["inputs"]), case["expected"]))
            else:
                python_cases.append(PythonCase(str(case["case_id"]), dict(case["inputs"])))
        differential = verify_differential(source, tuple(python_cases))
        if not differential["passed"]:
            raise SkillBundleError(f"skill {skill.get('skill_id')} differential replay failed")
    if not content_digest_matches(bundle):
        raise SkillBundleError("skill bundle content digest mismatch")
    return {
        "status": "PASS",
        "content_sha256": bundle["content_sha256"],
        "skill_count": len(skills),
    }

def skill_contracts_from_bundle(bundle: Mapping[str, Any]) -> tuple[Skill, ...]:
    """Convert a verified portable bundle into canonical ``Skill`` contracts."""
    try:
        verification = verify_skill_bundle(bundle)
        bundle_sha256 = str(verification["content_sha256"])
        skills = bundle["skills"]
        contracts: list[Skill] = []
        for row in skills:
            if not isinstance(row, Mapping):
                raise SkillBundleError("skill row is not an object")
            cases = row["cases"]
            parameters = row["parameters"]
            contracts.append(
                Skill(
                    skill_id=str(row["skill_id"]),
                    title=str(row["title"]),
                    domains=tuple(str(value) for value in row["domains"]),
                    input_schema={
                        "schema": "cassi.python.input.v1",
                        "parameters": list(parameters),
                        "case_ids": [str(case["case_id"]) for case in cases],
                    },
                    source_program=str(row["source"]),
                    canonical_ast=dict(row["program"]),
                    output_schema={
                        "schema": "cassi.python.output.v1",
                        "type": "runtime-value",
                    },
                    verification_cases=tuple(dict(case) for case in cases),
                    support_roots=(
                        f"skill-bundle:{bundle_sha256}",
                        f"program:{row['program_sha256']}",
                        f"cases:{row['cases_sha256']}",
                    ),
                    applicability_guards=("cassi-python-v1",),
                    resource_budget={"verification_cases": len(cases)},
                    revision_id=bundle_sha256,
                )
            )
        return tuple(contracts)
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, SkillBundleError):
            raise
        raise SkillBundleError("skill bundle cannot be converted to canonical contracts") from exc


def write_skill_bundle(path: Path, bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
    value = dict(bundle or build_skill_bundle())
    verification = verify_skill_bundle(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return verification


def load_skill_bundle(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillBundleError(f"cannot load skill bundle: {path}") from exc
    if not isinstance(value, Mapping):
        raise SkillBundleError("skill bundle root is not an object")
    verify_skill_bundle(value)
    return dict(value)


__all__ = [
    "SKILL_BUNDLE_SCHEMA",
    "SkillBundleError",
    "build_skill_bundle",
    "load_skill_bundle",
    "skill_contracts_from_bundle",
    "verify_skill_bundle",
    "write_skill_bundle",
]
