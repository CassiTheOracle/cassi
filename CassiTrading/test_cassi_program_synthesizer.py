from __future__ import annotations

import unittest

from cassi_program_synthesizer import (
    ProgramSynthesizer,
    SynthesisBudget,
    SynthesisError,
)
from cassi_skill_bundle import build_skill_bundle, skill_contracts_from_bundle


class RecordingField:
    def __init__(self) -> None:
        self.predictions: list[tuple[str, str]] = []
        self.updates: list[tuple[str, str, str]] = []

    def predict(self, signature: str, mutation: str) -> dict[str, object]:
        self.predictions.append((signature, mutation))
        outcome = "promote" if mutation.endswith("/scale") else "reject"
        return {"status": "supported", "outcome": outcome, "score": 1.0 if outcome == "promote" else 0.0}

    def learn(self, signature: str, mutation: str, outcome: str) -> None:
        if len(self.predictions) <= len(self.updates):
            raise AssertionError("field learned before prediction")
        self.updates.append((signature, mutation, outcome))


class ProgramSynthesizerTests(unittest.TestCase):
    def test_typed_grammar_generates_verified_candidates_and_uses_field_preference(self) -> None:
        skills = skill_contracts_from_bundle(build_skill_bundle())
        field = RecordingField()
        receipt = ProgramSynthesizer(budget=SynthesisBudget(max_candidates=4)).synthesize(
            [skills[1]],
            task_id="math-composition",
            evidence_roots=("holdout:math",),
            field=field,
            learn_field=True,
        )
        self.assertEqual(receipt["schema"], "cassi.market-program-synthesis.v1")
        self.assertEqual(receipt["frontier"]["candidate_count"], 4)
        self.assertEqual(receipt["selected"]["mutation"], "P1/scale")
        self.assertEqual(len(field.predictions), 4)
        self.assertEqual(len(field.updates), 4)
        self.assertTrue(all(row[2] == "supported" for row in field.updates))
        self.assertTrue(all(row["outcome"] == "supported" for row in receipt["frontier"]["candidates"]))
        self.assertTrue(all("holdout:math" in row["program"]["evidence_roots"] for row in receipt["frontier"]["candidates"]))

    def test_prediction_before_update_and_replay_are_deterministic(self) -> None:
        skill = skill_contracts_from_bundle(build_skill_bundle())[0]
        first = ProgramSynthesizer().synthesize([skill], task_id="deterministic")
        second = ProgramSynthesizer().synthesize([skill], task_id="deterministic")
        self.assertEqual(first["frontier_sha256"], second["frontier_sha256"])
        self.assertEqual(first["selected"]["program_sha256"], second["selected"]["program_sha256"])

    def test_source_budget_fails_closed(self) -> None:
        skill = skill_contracts_from_bundle(build_skill_bundle())[0]
        with self.assertRaises(SynthesisError):
            ProgramSynthesizer(budget=SynthesisBudget(max_source_chars=4)).synthesize(
                [skill],
                task_id="too-small",
            )

    def test_identity_operator_preserves_non_numeric_skill_types(self) -> None:
        skill = skill_contracts_from_bundle(build_skill_bundle())[7]
        receipt = ProgramSynthesizer().synthesize([skill], task_id="structured-identity")
        self.assertEqual(receipt["frontier"]["candidate_count"], 1)
        self.assertEqual(receipt["selected"]["mutation"], "P7/identity")
        self.assertEqual(receipt["selected"]["program"]["typed_outputs"]["type"], "record")
        self.assertEqual(receipt["selected"]["outcome"], "supported")


if __name__ == "__main__":
    unittest.main(verbosity=2)
