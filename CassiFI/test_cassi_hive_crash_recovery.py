from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from cassi_field_atlas import FieldProgram, PrimitiveStep
from cassi_field_hive import (
    ExperienceCandidate,
    ExperienceEvidence,
    Review,
    build_knowledge_bundle,
)
from cassi_hive_coordinator import HiveCoordinator
from cassi_hive_runtime import HiveField
from cassi_hive_store import LocalHiveStore, decode_bundle


_CRASH_SCRIPT = r'''
import json
import os
import sys
from pathlib import Path

import cassi_hive_store as store_module
from cassi_hive_store import LocalHiveStore, decode_bundle

root = Path(sys.argv[1])
mode = sys.argv[2]
bundle = decode_bundle(json.loads((root / "bundle.json").read_text(encoding="utf-8")))
if mode == "unindexed":
    original_atomic_write = store_module._atomic_write

    def crash_after_object(path, payload):
        original_atomic_write(path, payload)
        os._exit(83)

    store_module._atomic_write = crash_after_object
    with LocalHiveStore(root / "hive", hive_id="main") as store:
        store.put_document(bundle.as_dict())
elif mode == "unpublished":
    with LocalHiveStore(root / "hive", hive_id="main") as store:
        store.put_document(bundle.as_dict())
        os._exit(83)
elif mode == "committed":
    with LocalHiveStore(root / "hive", hive_id="main") as store:
        store.publish_bundle(bundle, expected_generation=0)
        os._exit(83)
else:
    raise SystemExit("unknown crash mode")
'''


_RACE_PUBLISHER_SCRIPT = r'''
import json
import sys
import time
from pathlib import Path

from cassi_hive_store import HiveStoreError, LocalHiveStore, decode_bundle

root = Path(sys.argv[1])
publisher_id = sys.argv[2]
(root / ("ready-" + publisher_id)).write_text("ready", encoding="utf-8")
while not (root / "race-start").exists():
    time.sleep(0.001)
with LocalHiveStore(root / "hive", hive_id="main") as store:
    bundle = decode_bundle(
        json.loads((root / ("bundle-" + publisher_id + ".json")).read_text(encoding="utf-8"))
    )
    try:
        object_id = store.publish_bundle(bundle, expected_generation=0)
    except HiveStoreError as exc:
        result = {"status": "conflict", "error": str(exc)}
    else:
        result = {"status": "won", "object_id": object_id}
print(json.dumps(result, sort_keys=True))
'''


def _launch_race_publisher(root: Path, publisher_id: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", _RACE_PUBLISHER_SCRIPT, str(root), publisher_id],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_race_publishers(root: Path, publisher_ids: tuple[str, ...]) -> None:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if all((root / ("ready-" + publisher_id)).exists() for publisher_id in publisher_ids):
            return
        time.sleep(0.01)
    raise AssertionError("race publishers did not reach the start barrier")


def _finish_race_publisher(process: subprocess.Popen[str], publisher_id: str) -> dict[str, object]:
    stdout, stderr = process.communicate(timeout=180)
    assert process.returncode == 0, (
        f"race publisher {publisher_id!r} failed with {process.returncode}:\n"
        f"stdout={stdout}\nstderr={stderr}"
    )
    return json.loads(stdout.strip().splitlines()[-1])


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _prepare_bundle(root: Path) -> object:
    with HiveField.open(
        root / "scout",
        hive_home=root / "hive",
        instance_id="scout",
        mode="scout",
        metadata={"test_name": "crash-recovery", "arm": "scout"},
    ) as field:
        program = FieldProgram(
            program_id="crash-recovery-program",
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
            support_event_ids=(_digest("support"),),
            assessment_ids=(_digest("assessment"),),
            held_out_results=({"loss": 0.0, "label": "crash-recovery"},),
            counterexamples=(),
            derivation_roots=(),
        )
        transition = field.raw_owner.configure_program("crash-recovery:configure", program)
        field.publish_experience(
            transition=transition.as_dict(),
            task_id="crash-recovery-publish",
            context={"domain": "crash-recovery"},
            action={"operation": "configure-program"},
            prediction={"program_id": program.program_id},
            outcome={"program_id": program.program_id, "status": "configured"},
            candidate=candidate,
            evidence=evidence,
        )

    with LocalHiveStore(root / "hive", hive_id="main") as store:
        coordinator = HiveCoordinator(store, leader_instance_id="leader")
        group = coordinator.groups()[0]
        for reviewer_id in ("reviewer-a", "reviewer-b"):
            coordinator.review(
                Review(
                    reviewer_instance_id=reviewer_id,
                    review_type="independent-reproduction",
                    result="supports",
                    evidence_ids=(_digest(reviewer_id),),
                ),
                candidate_id=group.candidate_id,
            )
        return build_knowledge_bundle(
            group.capsules,
            leader_instance_id="leader",
            authority_grant_sha256=_digest("grant"),
            predecessor_common_generation=0,
            reviews=store.list_reviews(candidate_object_id=group.candidate_id),
            minimum_support_reviews=2,
        )


def _run_crash(root: Path, mode: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", _CRASH_SCRIPT, str(root), mode],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 83, (
        f"crash-injection phase {mode!r} returned {result.returncode}:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


def test_hive_recovers_across_object_and_commit_crash_windows() -> None:
    for mode in ("unindexed", "unpublished", "committed"):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = _prepare_bundle(root)
            (root / "bundle.json").write_text(json.dumps(bundle.as_dict()), encoding="utf-8")
            _run_crash(root, mode)

            with LocalHiveStore(root / "hive", hive_id="main") as store:
                audit_before = store.audit()
                if mode == "committed":
                    assert audit_before["clean"]
                    assert bundle.object_id in audit_before["published_bundle_ids"]
                    assert bundle.object_id not in audit_before["unpublished_bundle_ids"]
                else:
                    assert not audit_before["clean"]
                    assert bundle.object_id in audit_before["unpublished_bundle_ids"]
                    if mode == "unindexed":
                        assert bundle.object_id in audit_before["unindexed_object_ids"]
                        assert bundle.object_id in audit_before["orphaned_object_ids"]
                    else:
                        assert bundle.object_id not in audit_before["unindexed_object_ids"]
                if mode == "committed":
                    assert store.current_generation == 1
                    assert len(store.list_bundles()) == 1
                    assert store.publish_bundle(bundle, expected_generation=0) == bundle.object_id
                else:
                    assert store.current_generation == 0
                    assert store.list_bundles() == ()
                    assert store.publish_bundle(bundle, expected_generation=0) == bundle.object_id
                assert store.current_generation == 1
                assert len(store.list_bundles()) == 1
                assert decode_bundle(store.list_bundle_documents()[0]).object_id == bundle.object_id
                assert store.audit()["clean"]


def test_crashed_commit_is_idempotent_under_followup_cas_race() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        committed_bundle = _prepare_bundle(root)
        (root / "bundle.json").write_text(
            json.dumps(committed_bundle.as_dict()),
            encoding="utf-8",
        )
        _run_crash(root, "committed")

        with LocalHiveStore(root / "hive", hive_id="main") as store:
            group = HiveCoordinator(store, leader_instance_id="leader").groups()[0]
            competing_bundle = build_knowledge_bundle(
                group.capsules,
                leader_instance_id="competing-leader",
                authority_grant_sha256=_digest("competing-grant"),
                predecessor_common_generation=0,
                reviews=store.list_reviews(candidate_object_id=group.candidate_id),
                minimum_support_reviews=2,
            )
        assert competing_bundle.object_id != committed_bundle.object_id
        for publisher_id, bundle in (
            ("recovery-a", committed_bundle),
            ("competitor-b", competing_bundle),
            ("competitor-c", competing_bundle),
        ):
            (root / ("bundle-" + publisher_id + ".json")).write_text(
                json.dumps(bundle.as_dict()),
                encoding="utf-8",
            )

        publisher_ids = ("recovery-a", "competitor-b", "competitor-c")
        processes = tuple(_launch_race_publisher(root, publisher_id) for publisher_id in publisher_ids)
        _wait_for_race_publishers(root, publisher_ids)
        (root / "race-start").write_text("go", encoding="utf-8")
        results = tuple(
            _finish_race_publisher(process, publisher_id)
            for process, publisher_id in zip(processes, publisher_ids)
        )

        assert sorted(result["status"] for result in results) == ["conflict", "conflict", "won"]
        assert results[0]["object_id"] == committed_bundle.object_id
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            assert store.current_generation == 1
            assert len(store.list_bundles()) == 1
            assert store.list_bundles()[0].object_id == committed_bundle.object_id
