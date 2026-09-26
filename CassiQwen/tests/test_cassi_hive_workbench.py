from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


_CHILD = r'''
import json
import sys
from pathlib import Path

from cassi_field_qwen_workbench import CassiFieldWorkMemory
from cassi_hive_store import make_document

root = Path(sys.argv[1])
phase = sys.argv[2]
with CassiFieldWorkMemory(root / "field") as memory:
    before = memory.state_receipt()["state_sha256"]
    with memory.open_hive(
        hive_home=root / "hive",
        hive_id="main",
        instance_id="qwen-workbench",
        mode="isolated",
        metadata={"test_name": "qwen-hive-restart", "arm": phase},
    ) as hive:
        if phase == "write":
            object_id = hive.hive.put_document(
                make_document(
                    "test.qwen-hive.restart.v1",
                    {"marker": "survives-process-restart", "phase": phase},
                )
            )
            payload = {"object_id": object_id}
        else:
            object_id = hive.hive.list_documents(schema="test.qwen-hive.restart.v1")[0]["object_id"]
            payload = {
                "document": hive.hive.get_document(object_id),
                "object_id": object_id,
                "object_count": hive.status()["hive"]["object_count"],
                "generation": hive.status()["hive"]["current_generation"],
            }
    after = memory.state_receipt()["state_sha256"]
print(json.dumps({"before": before, "after": after, **payload}, sort_keys=True))
'''


def _run_phase(root: Path, phase: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, str(root), phase],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        f"hive child phase {phase!r} failed with {result.returncode}:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_qwen_workbench_hive_survives_process_restart() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        written = _run_phase(root, "write")
        reopened = _run_phase(root, "read")

        assert written["object_id"] == reopened["object_id"]
        assert written["before"] == written["after"]
        assert reopened["before"] == written["after"]
        assert reopened["document"]["content"]["marker"] == "survives-process-restart"
        assert reopened["object_count"] >= 1
        assert reopened["generation"] == 0


def test_qwen_workbench_adopts_portable_field_program() -> None:
    from cassi_field_qwen_workbench import CassiFieldWorkMemory
    from cassi_field_atlas import FieldProgram, PrimitiveStep, sha256_value
    from cassi_field_hive import ExperienceCandidate, ExperienceEvidence
    from cassi_hive_promotion import PromotionLoop, ReviewerDecision
    from cassi_hive_runtime import HiveField
    from cassi_hive_store import LocalHiveStore
    with TemporaryDirectory() as directory:
        root = Path(directory)
        program = FieldProgram(
            program_id="qwen-portable-program",
            version=1,
            roles=("source",),
            steps=(PrimitiveStep(operation="identity", output="result", inputs=("source",)),),
            outputs=("result",),
        )
        with HiveField.open(
            root / "scout",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="native-scout",
            mode="scout",
        ) as scout:
            transition = scout.raw_owner.configure_program("configure:qwen-portable", program)
            scout.publish_experience(
                transition=transition.as_dict(),
                task_id="qwen-portable",
                context={"domain": "qwen-compatibility"},
                action={"operation": "configure-program"},
                prediction={"program_id": program.program_id},
                outcome={"status": "configured"},
                candidate=ExperienceCandidate(
                    kind="field-program",
                    object={"portable_transfer": True, "program": program.as_dict()},
                    operation_plan=(
                        {
                            "operation": "configure-program",
                            "program": program.as_dict(),
                        },
                    ),
                    guards=(),
                    dependencies=(),
                ),
                evidence=ExperienceEvidence(
                    support_event_ids=(sha256_value("qwen-portable-support"),),
                    assessment_ids=(sha256_value("qwen-portable-assessment"),),
                    held_out_results=({"status": "configured"},),
                    counterexamples=(),
                    derivation_roots=(),
                ),
            )

        with LocalHiveStore(root / "hive", hive_id="main") as store:
            loop = PromotionLoop(store, leader_instance_id="leader")
            candidate_id = loop.coordinator.groups()[0].candidate_id
            loop.review(
                candidate_id,
                (
                    ReviewerDecision("reviewer-a", "supports"),
                    ReviewerDecision("reviewer-b", "supports"),
                ),
            )
            report = loop.run_once()
            assert len(report.promoted_bundle_ids) == 1

        with CassiFieldWorkMemory(root / "qwen") as memory:
            with memory.open_hive(
                hive_home=root / "hive",
                hive_id="main",
                instance_id="qwen-member",
                mode="member",
            ) as hive:
                assert hive.status()["common_generation"] == 1
            assert any(
                row.program_id == "qwen-portable-program"
                for row in memory.owner.state.programs
            )
