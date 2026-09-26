from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from cassi_field_hive import Review, build_knowledge_bundle
from cassi_hive_coordinator import HiveCoordinator
from cassi_hive_store import LocalHiveStore, decode_bundle


_WORKER_SCRIPT = r'''
import hashlib
import json
import sys
from pathlib import Path

from cassi_field_atlas import FieldProgram, PrimitiveStep
from cassi_field_hive import ExperienceCandidate, ExperienceEvidence
from cassi_hive_runtime import HiveField

root = Path(sys.argv[1])
instance_id = sys.argv[2]
def digest(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()
program = FieldProgram(
    program_id="concurrent-program",
    version=1,
    roles=("source",),
    steps=(PrimitiveStep(operation="identity", output="result", inputs=("source",)),),
    outputs=("result",),
)
candidate = ExperienceCandidate(
    kind="field-program",
    object=program.as_dict(),
    operation_plan=({"operation": "configure-program", "program": program.as_dict()},),
    guards=(),
    dependencies=(),
)
evidence = ExperienceEvidence(
    support_event_ids=(digest(instance_id + ":support"),),
    assessment_ids=(digest(instance_id + ":assessment"),),
    held_out_results=({"loss": 0.0, "label": instance_id},),
    counterexamples=(),
    derivation_roots=(),
)
with HiveField.open(
    root / instance_id,
    hive_home=root / "hive",
    instance_id=instance_id,
    mode="scout",
    metadata={"test_name": "concurrent-worker", "arm": instance_id},
) as field:
    transition = field.raw_owner.configure_program(instance_id + ":configure", program)
    capsule = field.publish_experience(
        transition=transition.as_dict(),
        task_id="concurrent-publish",
        context={"domain": "concurrency"},
        action={"operation": "configure-program"},
        prediction={"program_id": program.program_id},
        outcome={"program_id": program.program_id, "status": "configured"},
        candidate=candidate,
        evidence=evidence,
    )
print(json.dumps({"capsule_id": capsule.object_id}, sort_keys=True))
'''

_PUBLISHER_SCRIPT = r'''
import json
import sys
import time
from pathlib import Path

from cassi_hive_store import HiveStoreError, LocalHiveStore, decode_bundle

root = Path(sys.argv[1])
ready = root / ("ready-" + sys.argv[2])
start = root / "start-publish"
ready.write_text("ready", encoding="utf-8")
while not start.exists():
    time.sleep(0.001)
with LocalHiveStore(root / "hive", hive_id="main") as store:
    bundle = decode_bundle(
        json.loads((root / ("bundle-" + sys.argv[2] + ".json")).read_text(encoding="utf-8"))
    )
    try:
        object_id = store.publish_bundle(bundle, expected_generation=0)
    except HiveStoreError as exc:
        result = {"status": "conflict", "error": str(exc)}
    else:
        result = {"status": "won", "object_id": object_id}
print(json.dumps(result, sort_keys=True))
'''


def _run_worker(root: Path, instance_id: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", _WORKER_SCRIPT, str(root), instance_id],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        f"worker {instance_id!r} failed with {result.returncode}:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def _launch_publisher(root: Path, publisher_id: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", _PUBLISHER_SCRIPT, str(root), publisher_id],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_ready(root: Path, publisher_ids: tuple[str, ...]) -> None:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if all((root / ("ready-" + publisher_id)).exists() for publisher_id in publisher_ids):
            return
        time.sleep(0.01)
    raise AssertionError("concurrent publishers did not reach the start barrier")


def _finish_publisher(process: subprocess.Popen[str], publisher_id: str) -> dict[str, object]:
    stdout, stderr = process.communicate(timeout=180)
    assert process.returncode == 0, (
        f"publisher {publisher_id!r} failed with {process.returncode}:\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
    return json.loads(stdout.strip().splitlines()[-1])


def test_concurrent_field_workers_have_one_cas_bundle_winner() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        worker_a = _run_worker(root, "worker-a")
        worker_b = _run_worker(root, "worker-b")
        assert worker_a["capsule_id"] != worker_b["capsule_id"]

        with LocalHiveStore(root / "hive", hive_id="main") as store:
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            group = coordinator.groups()[0]
            for reviewer_id in ("reviewer-a", "reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer_id,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(hashlib.sha256(reviewer_id.encode("utf-8")).hexdigest(),),
                    ),
                    candidate_id=group.candidate_id,
                )
            common_reviews = store.list_reviews(candidate_object_id=group.candidate_id)
            bundles = tuple(
                build_knowledge_bundle(
                    group.capsules,
                    leader_instance_id=leader_id,
                    authority_grant_sha256=hashlib.sha256((leader_id + "-grant").encode("utf-8")).hexdigest(),
                    predecessor_common_generation=0,
                    reviews=common_reviews,
                    minimum_support_reviews=2,
                )
                for leader_id in ("leader-a", "leader-b")
            )
            for publisher_id, bundle in zip(("publisher-a", "publisher-b"), bundles):
                (root / (f"bundle-{publisher_id}.json")).write_text(
                    json.dumps(bundle.as_dict()),
                    encoding="utf-8",
                )

        publisher_ids = ("publisher-a", "publisher-b")
        processes = tuple(_launch_publisher(root, publisher_id) for publisher_id in publisher_ids)
        _wait_for_ready(root, publisher_ids)
        (root / "start-publish").write_text("go", encoding="utf-8")
        results = tuple(
            _finish_publisher(process, publisher_id)
            for process, publisher_id in zip(processes, publisher_ids)
        )

        assert sorted(result["status"] for result in results) == ["conflict", "won"]
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            assert store.current_generation == 1
            assert len(store.list_bundles()) == 1
            assert decode_bundle(store.list_bundle_documents()[0]).object_id in {
                bundles[0].object_id,
                bundles[1].object_id,
            }
