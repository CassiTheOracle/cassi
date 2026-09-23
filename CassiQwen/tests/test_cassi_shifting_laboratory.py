"""The Shifting Laboratory, end to end: hidden worlds, shifts, and authoring.

The expensive artifacts (a full hidden course, the shift canary, the authoring
canary) are built once per session and shared; everything else is judged
directly so a failure names the check that moved.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import unittest
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from laboratory import authoring as authoring_module
from laboratory import hidden as hidden_module
from laboratory import shifting as shifting_module
from laboratory import stations as stations_module
from laboratory.course import Course, CourseContext, EntityAgent, ScriptedAgent

CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
RUNNER = CASSIQWEN_ROOT / "run_shifting_laboratory.py"
LAW = "L3-native-w49"


# --------------------------------------------------------------------------- #
# shared artifacts
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=None)
def world(law_id: str = LAW, variant: str = "hidden-1") -> hidden_module.HiddenWorld:
    return hidden_module.hidden_world(true_law_id=law_id, variant=variant)


def run_course(world_: hidden_module.HiddenWorld, answerer: Any, stations: Any = None) -> dict[str, Any]:
    agent = ScriptedAgent(answerer=answerer, kind="test")
    course = Course(
        world_,
        world_.stations() if stations is None else stations,
        level="hidden" if stations is None else "authoring",
        world_block=world_.declared_world(),
        title=world_.title(),
    )
    return course.run(agent, deadline_s=900.0)


@lru_cache(maxsize=None)
def honest_receipt() -> dict[str, Any]:
    return run_course(world(), hidden_module.competent_agent())


@lru_cache(maxsize=None)
def shift_report() -> dict[str, Any]:
    return shifting_module.shift_canary_report()


@lru_cache(maxsize=None)
def authoring_report() -> dict[str, Any]:
    return authoring_module.authoring_canary_report()


def station_receipt(receipt: Mapping[str, Any], station_id: str) -> Mapping[str, Any]:
    return next(item for item in receipt["stations"] if item["station"] == station_id)


def context(world_: hidden_module.HiddenWorld) -> CourseContext:
    mission = stations_module.mission_document(
        world_,
        world_.stations(),
        level="hidden",
        world=world_.declared_world(),
        title=world_.title(),
    )
    return CourseContext(fixture=world_, mission=mission)


def check_named(report: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return next(item for item in report["checks"] if item["name"] == name)


# --------------------------------------------------------------------------- #
# the hidden stations
# --------------------------------------------------------------------------- #


class HiddenStationTest(unittest.TestCase):
    def test_the_honest_reader_identifies_the_law_and_names_the_longest_write(self) -> None:
        receipt = honest_receipt()
        self.assertEqual(receipt["verdict"], "pass")
        self.assertEqual(receipt["station_verdicts"], {"identification": "pass", "retention": "pass"})

        identification = station_receipt(receipt, "identification")
        evidence = identification["evidence"]
        self.assertEqual(evidence["law_id"], world().true_law_id)

        measured = float(evidence["measured"]["value"])
        truth = world().probe_omega(world().true_law)
        self.assertLess(abs(measured - truth), hidden_module.MEASUREMENT_TOLERANCE)
        self.assertEqual(evidence["measured"]["recipe_id"], world().measurement_recipe_id)

        forecast = evidence["forecast"]
        self.assertEqual([int(step) for step in forecast["steps"]], list(hidden_module.FORECAST_STEPS))
        expected = world().forecast_truth(world().true_law)
        for claimed, actual in zip(forecast["psi_y"], expected):
            self.assertLess(abs(float(claimed) - float(actual)), 1e-6)

        retention = station_receipt(receipt, "retention")
        claims = {item["recipe_id"]: item for item in retention["evidence"]["recipes"]}
        truth_lifetimes = world().retention_lifetimes()
        self.assertEqual(retention["evidence"]["longest"], "R4-counterflow")
        for recipe_id, value in truth_lifetimes.items():
            self.assertEqual(claims[recipe_id]["claim"], "measured")
            self.assertAlmostEqual(float(claims[recipe_id]["tau_seconds"]), float(value), places=3)

    def test_the_forecast_check_holds_the_declared_tolerance(self) -> None:
        world_ = world()
        identification, _ = world_.stations()
        evidence = hidden_module.competent_agent()(identification.brief)
        self.assertEqual(identification.judge(context(world_), evidence)["verdict"], "pass")

        scale = world_.forecast_scale()
        tolerance = hidden_module.FORECAST_TOLERANCE * scale
        for factor, expected in ((0.5, True), (1.5, False)):
            moved = json.loads(json.dumps(evidence))
            moved["forecast"]["psi_y"][0] = float(moved["forecast"]["psi_y"][0]) + factor * tolerance
            report = identification.judge(context(world_), moved)
            named = check_named(report, "the held-out forecast matches the field")
            self.assertEqual(named["ok"], expected, json.dumps(named["numbers"], sort_keys=True))

    def test_a_wrong_law_is_refused_by_the_named_check(self) -> None:
        world_ = world()
        identification, _ = world_.stations()
        wrong = "L1-native-w25"
        evidence = hidden_module.competent_agent()(identification.brief)
        evidence["law_id"] = wrong
        report = identification.judge(context(world_), evidence)
        self.assertEqual(report["verdict"], "fail")
        self.assertFalse(check_named(report, "the identified law is the law that ran the observations")["ok"])

        receipt = run_course(world_, hidden_module.misattributing_agent())
        self.assertEqual(receipt["verdict"], "fail")
        failed = station_receipt(receipt, "identification")
        self.assertIn(
            "the identified law is the law that ran the observations",
            [check["name"] for check in failed["checks"] if not check["ok"]],
        )
        # the runner-up reader is wrong about the law but honest about the instrument:
        # its measurement is the real fit and its forecast belongs to another law
        self.assertNotEqual(failed["evidence"]["law_id"], world_.true_law_id)
        self.assertIn(failed["evidence"]["law_id"], [law["law_id"] for law in world_.laws])
        self.assertAlmostEqual(
            float(failed["evidence"]["measured"]["value"]),
            float(failed["measurements"]["judge_omega"]),
            places=6,
        )
        tolerance = hidden_module.FORECAST_TOLERANCE * world_.forecast_scale()
        gap = max(
            abs(float(claimed) - float(actual))
            for claimed, actual in zip(
                failed["evidence"]["forecast"]["psi_y"], failed["measurements"]["true_forecast"]
            )
        )
        self.assertGreaterEqual(gap, tolerance)

    def test_a_write_that_outlives_the_horizon_must_be_claimed_as_such(self) -> None:
        # R1 uniform is measured on three laws and never falls to the threshold on L4.
        menu = [
            hidden_module.recipe_document("R1-uniform-pair", "uniform-pair", {"psi_y": 1.0, "psi_i": 0.0}),
            hidden_module.recipe_document(
                "R3-narrow-packet", "counterflow-packet",
                {"amplitude": 0.8, "width": 1.0, "center": 11.5, "speed": 0.4},
            ),
        ]
        world_ = hidden_module.hidden_world(
            true_law_id="L4-equal-w81", variant="hidden-beyond", retention_menu=menu
        )
        lifetimes = world_.retention_lifetimes()
        self.assertIsNone(lifetimes["R1-uniform-pair"])
        self.assertIsNotNone(lifetimes["R3-narrow-packet"])

        _, retention = world_.stations()
        evidence = hidden_module.competent_agent()(retention.brief)
        report = retention.judge(context(world_), evidence)
        self.assertEqual(report["verdict"], "pass", json.dumps(report["checks"], sort_keys=True))
        self.assertEqual(evidence["longest"], "R1-uniform-pair")

        as_measured = json.loads(json.dumps(evidence))
        for item in as_measured["recipes"]:
            if item["recipe_id"] == "R1-uniform-pair":
                item["claim"] = "measured"
                item["tau_seconds"] = 50.0
        report = retention.judge(context(world_), as_measured)
        self.assertEqual(report["verdict"], "fail")
        self.assertFalse(check_named(report, "every write's lifetime matches the declared procedure")["ok"])

    def test_a_lifetime_claim_outside_the_tolerance_is_refused(self) -> None:
        world_ = world()
        _, retention = world_.stations()
        evidence = hidden_module.competent_agent()(retention.brief)
        truth = world_.retention_lifetimes()["R3-narrow-packet"]
        tolerance = max(
            hidden_module.RETENTION_RELATIVE_TOLERANCE * float(truth),
            hidden_module.RETENTION_ABSOLUTE_TOLERANCE,
        )
        inside = json.loads(json.dumps(evidence))
        outside = json.loads(json.dumps(evidence))
        for item in inside["recipes"]:
            if item["recipe_id"] == "R3-narrow-packet":
                item["tau_seconds"] = float(truth) + 0.9 * tolerance
        for item in outside["recipes"]:
            if item["recipe_id"] == "R3-narrow-packet":
                item["tau_seconds"] = float(truth) + 1.1 * tolerance

        self.assertEqual(retention.judge(context(world_), inside)["verdict"], "pass")
        report = retention.judge(context(world_), outside)
        self.assertEqual(report["verdict"], "fail")
        named = check_named(report, "every write's lifetime matches the declared procedure")
        numbers = named["numbers"]["R3-narrow-packet"]
        self.assertAlmostEqual(float(numbers["tolerance"]), tolerance, places=9)
        self.assertGreater(float(numbers["absolute_error"]), tolerance)

    def test_every_declared_law_has_the_analytic_frequency_it_claims(self) -> None:
        # the Level-2 instrument is the same conversion frequency the physics
        # course declares: the Yin gain enters as 1 + phi for the native
        # convention and as 1 + phi^2 when both channels convert equally
        for law in hidden_module.LAW_MENU:
            world_ = hidden_module.hidden_world(true_law_id=law["law_id"])
            gain = hidden_module.PHI if law["yin"] == "phi" else hidden_module.PHI ** 2
            analytic = math.sqrt((1.0 + gain) * float(law["omega2"]))
            measured = world_.probe_omega(world_.true_law)
            self.assertLess(abs(measured - analytic) / analytic, 1e-4, law["law_id"])

    def test_the_identification_station_reports_a_readable_instrument(self) -> None:
        world_ = world()
        identification, _ = world_.stations()
        report = identification.judge(context(world_), hidden_module.competent_agent()(identification.brief))
        control = next(
            item
            for item in report["controls"]
            if item["name"] == "the declared instrument can read its own observation"
        )
        self.assertTrue(control["ok"])
        self.assertLess(
            float(control["numbers"]["residual_relative"]), hidden_module.MEASUREMENT_RESIDUAL_FLOOR
        )


# --------------------------------------------------------------------------- #
# the shift
# --------------------------------------------------------------------------- #


class ShiftTest(unittest.TestCase):
    def test_a_tracking_reader_notices_the_switch_and_a_frozen_reader_does_not(self) -> None:
        report = shift_report()
        self.assertTrue(report["discriminates"], json.dumps(sorted(report["readers"]), sort_keys=True))
        readers = report["readers"]
        self.assertEqual(set(readers), set(shifting_module.SHIFT_READERS))

        tracking = readers["tracking"]
        self.assertEqual(tracking["verdict"], "pass")
        self.assertEqual(tracking["detection"]["latency"], 0)
        self.assertEqual(tracking["detection"]["stale_rounds_after_switch"], 0)
        self.assertEqual(tracking["detection"]["correct_rounds"], [3, 4, 5])

        static = readers["static"]
        self.assertEqual(static["verdict"], "fail")
        self.assertFalse(static["detection"]["detected"])
        # the round at the switch carries the shift error; the rounds after it stay stale
        self.assertEqual(
            static["detection"]["stale_rounds_after_switch"],
            static["detection"]["rounds_after_switch"] - 1,
        )
        self.assertGreaterEqual(static["carry"]["at_switch"], shifting_module.CARRY_FLOOR)
        self.assertAlmostEqual(static["carry"]["max_after_switch"], static["carry"]["at_switch"], places=6)
        self.assertLess(tracking["carry"]["max_after_switch"], shifting_module.CARRY_FLOOR)

        shortcut = readers["shortcut"]
        self.assertEqual(shortcut["verdict"], "fail")
        self.assertFalse(shortcut["detection"]["detected"])
        self.assertTrue(all(control["ok"] for control in tracking["controls"]))

    def test_a_shift_refuses_to_change_its_reader_or_its_plan(self) -> None:
        plan = shifting_module.ShiftPlan(
            ("L1-native-w25", "L1-native-w25", "L3-native-w49"), 2, variant="shift-guard"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "guard.json"
            shifting_module.ShiftingShift(
                plan, state_path=state, receipt_dir=root / "receipts"
            ).run(shifting_module.scripted_factory("tracking"), deadline_s=900.0)

            with self.assertRaises(stations_module.LaboratoryError):
                shifting_module.ShiftingShift(
                    plan, state_path=state, receipt_dir=root / "receipts"
                ).run(shifting_module.scripted_factory("static"), deadline_s=900.0)

            other = shifting_module.ShiftPlan(
                ("L1-native-w25", "L1-native-w25", "L4-equal-w81"), 2, variant="shift-guard"
            )
            with self.assertRaises(stations_module.LaboratoryError):
                shifting_module.ShiftingShift(
                    other, state_path=state, receipt_dir=root / "receipts"
                ).run(shifting_module.scripted_factory("tracking"), deadline_s=900.0)

    def test_a_shift_resumes_and_keeps_its_digest(self) -> None:
        # round 2 is the first round that runs the new law
        plan = shifting_module.ShiftPlan(
            ("L1-native-w25", "L1-native-w25", "L3-native-w49"), 2, variant="shift-test"
        )
        factory = shifting_module.scripted_factory("tracking")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = shifting_module.ShiftingShift(
                plan, state_path=root / "a.json", receipt_dir=root / "receipts-a"
            ).run(factory, deadline_s=900.0)
            second = shifting_module.ShiftingShift(
                plan, state_path=root / "b.json", receipt_dir=root / "receipts-b"
            ).run(factory, deadline_s=900.0)
            resumed = shifting_module.ShiftingShift(
                plan, state_path=root / "a.json", receipt_dir=root / "receipts-a"
            ).run(factory, deadline_s=900.0)

        self.assertEqual(first["verdict"], "pass")
        self.assertEqual(first["settled"], first["declared_rounds"])
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(first["digest"], resumed["digest"])
        self.assertIsNone(first["resumed_from"])
        self.assertEqual(resumed["resumed_from"], [0, 1, 2])
        self.assertEqual(
            [item["claimed_law"] for item in resumed["rounds"]],
            [str(world.true_law_id) for world in plan.worlds()],
        )
        self.assertEqual(
            [item["receipt"] for item in resumed["rounds"]],
            ["round-000.json", "round-001.json", "round-002.json"],
        )
        # the carry at the switch is the declared separation of the two laws
        self.assertAlmostEqual(
            float(first["carry"]["at_switch"]),
            float(first["controls"][1]["numbers"]["relative_move"]),
            delta=1e-5,
        )


# --------------------------------------------------------------------------- #
# authoring
# --------------------------------------------------------------------------- #


class AuthoringTest(unittest.TestCase):
    def test_a_discriminating_proposal_is_accepted_and_a_blind_one_is_refused(self) -> None:
        report = authoring_report()
        self.assertTrue(report["discriminates"])
        good = report["runs"]["good"]
        self.assertEqual(good["verdict"], "pass")
        self.assertTrue(all(check["ok"] for check in good["checks"]))
        self.assertEqual(good["measurements"]["authored_world"]["true_lifetimes"]["R3-narrow-packet"], 1.1)

        blind = report["runs"]["blind"]
        self.assertEqual(blind["verdict"], "fail")
        named = {check["name"]: check["ok"] for check in blind["checks"]}
        self.assertFalse(named["the authored station accepts the honest reader"])
        self.assertFalse(named["the authored world's own controls hold"])
        self.assertEqual(
            blind["measurements"]["authored_world"]["measured_recipe_id"], "counterflow-packet"
        )

    def test_an_undeclared_part_is_refused_before_anything_is_built(self) -> None:
        base = world()
        proposal = authoring_module.reference_proposals()["good"]
        broken = dict(proposal, observation_recipe_ids=["uniform-pair", "not-a-recipe"])
        report = authoring_module.judge_authoring(base, broken)
        self.assertEqual(report["verdict"], "fail")
        self.assertFalse(check_named(report, "the proposal uses only declared parts")["ok"])
        self.assertNotIn("readers", report["measurements"])

        unknown_law = dict(proposal, law_id="L9-imaginary")
        report = authoring_module.judge_authoring(base, unknown_law)
        self.assertEqual(report["verdict"], "fail")
        self.assertNotIn("readers", report["measurements"])

    def test_the_authored_station_is_judged_by_running_it(self) -> None:
        report = authoring_report()["runs"]["good"]["measurements"]
        readers = report["readers"]
        self.assertEqual(set(readers), set(authoring_module.AUTHOR_READERS))
        self.assertEqual(readers["honest"]["verdict"], "pass")
        self.assertEqual(readers["misattributing"]["verdict"], "fail")
        self.assertEqual(readers["unexecuted"]["verdict"], "fail")
        self.assertIn(
            "the identified law is the law that ran the observations",
            readers["misattributing"]["failed_checks"]["identification"],
        )
        self.assertTrue(all(control["ok"] for control in report["design_controls"]))


# --------------------------------------------------------------------------- #
# the mission as the entity's own obligation
# --------------------------------------------------------------------------- #


class RecordingProgramClient:
    """The program API as the mission agent uses it, with no server behind it."""

    def __init__(
        self,
        program: Mapping[str, Any] | None = None,
        frames: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.documents: list[dict[str, Any]] = []
        self.program = dict(program or {})
        self.frames = [dict(frame) for frame in frames]
        self.cursors: list[int] = []

    @staticmethod
    def _sample(method: str, path: str, payload: Any) -> Any:
        from cassi_program_benchmark_client import BenchmarkSample

        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return BenchmarkSample(
            method=method,
            path=path,
            status=200,
            payload=payload,
            raw_body=raw,
            content_type="application/json",
            elapsed_ns=0,
            request_body_bytes=0,
        )

    def create_program(self, **document: Any) -> Any:
        self.documents.append(dict(document))
        return self._sample(
            "POST", "/v1/programs", {"program_id": document["program_id"]}
        )

    def get_program(self, program_id: str) -> Any:
        return self._sample("GET", f"/v1/programs/{program_id}", self.program)

    def program_events(self, program_id: str, *, after: int = 0, **_: Any) -> Any:
        self.cursors.append(after)
        frames = [
            dict(frame) for frame in self.frames if int(frame.get("cursor", 0)) > after
        ]
        return self._sample("GET", f"/v1/programs/{program_id}/events", frames)


class MissionObligationTest(unittest.TestCase):
    def test_the_mission_deliverable_becomes_the_programs_own_obligation(self) -> None:
        world_ = world()
        mission = context(world_).mission
        client = RecordingProgramClient()
        with TemporaryDirectory() as directory:
            agent = EntityAgent(
                client=client,
                project_id="shifting-laboratory",
                allowed_roots=[directory],
                allowed_tools=("write_artifact",),
            )
            agent.start(mission)

        self.assertEqual(len(client.documents), 1)
        contract = client.documents[0]["deliverable"]
        self.assertEqual(contract["artifact"], "answer.json")
        self.assertEqual(contract["sections_key"], "stations")
        self.assertEqual(
            contract["sections"],
            [station["station_id"] for station in mission["stations"]],
        )
        self.assertEqual(contract["document_schema"], stations_module.MISSION_EVIDENCE_SCHEMA)
        self.assertEqual(contract["identity_key"], "fixture_id")
        self.assertEqual(contract["identity_value"], world_.fixture_id())

    def test_the_shift_reports_its_cycles_and_its_delivery_coverage(self) -> None:
        world_ = world()
        identification, _ = world_.stations()
        evidence = hidden_module.competent_agent()(identification.brief)
        mission = context(world_).mission
        document = {
            "schema": stations_module.MISSION_EVIDENCE_SCHEMA,
            "fixture_id": world_.fixture_id(),
            "stations": {identification.station_id: evidence},
        }
        frames = [
            {
                "cursor": 7,
                "event": "deliverable-advanced",
                "data": {
                    "kind": "deliverable-advanced",
                    "sequence": 7,
                    "payload": {
                        "covered": [identification.station_id],
                        "missing": ["retention"],
                        "source": "artifact",
                    },
                },
            }
        ]
        program = {
            "program_id": "lab-hidden-1",
            "status": "active",
            "cycles_completed": 4,
            "generation": 4,
            "deliverable": {"artifact": "answer.json", "sections": ["identification", "retention"]},
            "deliverable_state": {
                "complete": False,
                "covered": [identification.station_id],
                "missing": ["retention"],
            },
        }
        with TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspaces" / "lab-hidden-1"
            workspace.mkdir(parents=True)
            (workspace / "answer.json").write_text(
                "```json\n" + json.dumps(document) + "\n```\n", encoding="utf-8"
            )
            client = RecordingProgramClient(program=program, frames=frames)
            agent = EntityAgent(
                client=client,
                project_id="shifting-laboratory",
                allowed_roots=[directory],
                allowed_tools=("write_artifact",),
                workspace_root=workspace,
                poll_s=0.05,
            )
            agent.start(mission)
            produced = agent.evidence(
                [identification.station_id, "retention"], deadline_s=1.2
            )
            transcript = agent.transcript()

        # the deadline arrived with one station delivered, and the shift's own
        # record says exactly that
        self.assertEqual(set(produced), {identification.station_id})
        throughput = transcript["throughput"]
        self.assertEqual(throughput["cycles_completed"], 4)
        self.assertEqual(
            [row["covered"] for row in throughput["coverage"]],
            [[identification.station_id]],
        )
        self.assertEqual(throughput["deliverable_state"]["missing"], ["retention"])
        self.assertGreater(throughput["agent_seconds"], 0.0)
        self.assertAlmostEqual(
            throughput["seconds_per_cycle"],
            throughput["agent_seconds"] / 4,
            places=3,
        )


# --------------------------------------------------------------------------- #
# the runner
# --------------------------------------------------------------------------- #


class RunnerTest(unittest.TestCase):
    def run_mode(self, *arguments: str) -> tuple[int, Any]:
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(RUNNER), "--receipt-dir", directory, *arguments],
                cwd=CASSIQWEN_ROOT,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
        self.assertNotIn("Traceback", result.stderr, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_the_level_one_modes_still_pass(self) -> None:
        code, report = self.run_mode("self-check")
        self.assertEqual(code, 0)
        self.assertEqual(report["verdict"], "pass")

        code, report = self.run_mode("canary")
        self.assertEqual(code, 0)
        self.assertTrue(report["discriminates"])
        self.assertEqual(report["runs"]["competent"]["verdict"], "pass")

    def test_the_level_two_and_authoring_modes_are_wired(self) -> None:
        code, report = self.run_mode("discover", "--law", "L1-native-w25")
        self.assertEqual(code, 0)
        self.assertEqual(report["station_verdicts"], {"identification": "pass", "retention": "pass"})
        self.assertEqual(report["world"]["true_law_id"], "L1-native-w25")

        code, report = self.run_mode("author", "--reference", "blind")
        self.assertEqual(code, 1)
        self.assertEqual(report["station_verdicts"], {"authoring": "fail"})
        self.assertEqual(report["readers"]["honest"]["verdict"], "fail")


if __name__ == "__main__":
    unittest.main()
