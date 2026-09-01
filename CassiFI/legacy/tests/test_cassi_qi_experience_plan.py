"""Focused W10E/G10E and bounded W10A contract tests."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from cassi_qi_bootstrap import canonical_json_bytes
from run_cassi_qi_experience import (
    ExperienceExecutionError,
    execute_experience,
    run_experience,
    validate_experience_result,
)
from run_cassi_qi_experience_plan import (
    ExperiencePlanError,
    build_experience_plan,
    canonical_plan_bytes,
    materialize_plan_artifact,
    plan_self_sha256,
    plan_sha256,
    seal_experience_plan,
    validate_experience_plan,
)


_ZERO_POINT_FIVE = "f64:3fe0000000000000"
_ZERO_POINT_ONE = "f64:3fb999999999999a"


class ExperiencePlanContractTests(unittest.TestCase):
    def test_canonical_replay_and_hashes_are_stable(self) -> None:
        first = build_experience_plan()
        second = build_experience_plan()
        self.assertEqual(first, second)
        raw = canonical_plan_bytes(first)
        self.assertEqual(raw, canonical_plan_bytes(validate_experience_plan(raw)))
        self.assertEqual(first["plan_sha256"], plan_sha256(first))
        self.assertEqual(first["self_sha256"], plan_self_sha256(first))
        sealed, sealed_raw, raw_digest = seal_experience_plan(first)
        self.assertEqual(first, sealed)
        self.assertEqual(raw, sealed_raw)
        self.assertEqual(raw_digest, __import__("hashlib").sha256(raw).hexdigest())

    def test_missing_and_extra_fields_are_rejected(self) -> None:
        missing = build_experience_plan()
        missing.pop("codec_sha256")
        with self.assertRaises(ExperiencePlanError):
            validate_experience_plan(missing)
        extra = build_experience_plan()
        extra["unexpected"] = True
        with self.assertRaises(ExperiencePlanError):
            validate_experience_plan(extra)

    def test_parent_order_and_tampered_identity_are_rejected(self) -> None:
        plan = build_experience_plan()
        plan["consumed_semantic_subhashes"] = list(reversed(plan["consumed_semantic_subhashes"]))
        with self.assertRaises(ExperiencePlanError):
            validate_experience_plan(plan)
        tampered = build_experience_plan()
        tampered["plan_sha256"] = "0" * 64
        with self.assertRaises(ExperiencePlanError):
            validate_experience_plan(tampered)
    def test_materializer_rejects_falsey_explicit_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ExperiencePlanError):
                materialize_plan_artifact(root, {})
            self.assertFalse((root / "experience-plan.json").exists())

    def test_plan_artifact_is_not_rewritten_after_sealing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run_experience(build_experience_plan(), dependencies={}, output_root=root)
            original = (root / "experience-plan.json").read_bytes()
            with self.assertRaises(ExperienceExecutionError):
                run_experience(build_experience_plan(overrides={"plan_id": "id-changed-plan"}), dependencies={}, output_root=root)
            self.assertEqual(original, (root / "experience-plan.json").read_bytes())


class BoundedExperienceTests(unittest.TestCase):
    def _plan(self, *, minimum: int = 0, total_upper: str | None = None, per_event_upper: str | None = None) -> dict:
        plan = build_experience_plan()
        plan["stopping_rule"]["minimum_valid_episodes"] = minimum
        if total_upper is not None:
            plan["work_budgets"]["total"]["upper"] = total_upper
        if per_event_upper is not None:
            plan["work_budgets"]["per_event"]["upper"] = per_event_upper
        return build_experience_plan(payload=plan)

    def _dependencies(self, plan: dict, *, event_id: str = "event-1", controls=None):
        episode_id = plan["grounded_world_episode_streams"][0]["episode_id"]
        deps = {
            "initial_states": {episode_id: {"value": 0}},
            "events": {episode_id: [{"event_id": event_id, "value": 1}]},
            "advance": lambda state, event: {"state": {"value": state["value"] + event["value"]}, "work": 0.1, "committed": True},
        }
        if controls is not None:
            deps["controls"] = {episode_id: controls}
        return deps

    def test_missing_dependencies_are_accurately_blocked(self) -> None:
        result = execute_experience(build_experience_plan(), dependencies=None)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("missing canonical execution dependencies", result["reason"])
        self.assertEqual(result["raw_trace"], [])
        self.assertEqual(validate_experience_result(result)["result_sha256"], result["result_sha256"])

    def test_budget_stop_is_fail_closed_and_retains_stop_trace(self) -> None:
        plan = self._plan(total_upper=_ZERO_POINT_FIVE, per_event_upper="f64:3fa999999999999a")
        result = execute_experience(plan, dependencies=self._dependencies(plan))
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["stopped"])
        self.assertEqual(result["raw_trace"][0]["status"], "budget_stop")
        self.assertEqual(result["budget_used"], "f64:0000000000000000")

    def test_treatment_and_control_event_identity_cannot_overlap(self) -> None:
        plan = self._plan()
        episode_id = plan["grounded_world_episode_streams"][0]["episode_id"]
        result = execute_experience(
            plan,
            dependencies=self._dependencies(plan, controls=[{"event_id": "event-1", "value": 2}]),
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("identity overlap", result["reason"])
        self.assertEqual(result["episodes"], [])

    def test_bounded_execution_passes_only_after_declared_minimum(self) -> None:
        plan = self._plan(minimum=1)
        result = execute_experience(plan, dependencies=self._dependencies(plan))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["episodes"][0]["valid"], True)
        self.assertEqual(len(result["raw_trace"]), 1)
        self.assertEqual(validate_experience_result(result)["schema"], result["schema"])


if __name__ == "__main__":
    unittest.main()
