"""Extract and verify the packet decision trace a downstream consumer must cite.

A native or temporal consumer has to reference an identified packet decision, not
an arbitrary episode field. This runner drives the ordinary reasoning scenario,
then reads every episode scheduler trace out of the owner's task state and checks
each row's `snapshot_sha256` against a freshly computed digest of that row without
the digest field.

It answers one question: is the per-dispatch packet decision trace addressable,
self-consistent, and quotable by identity? It maps nothing onto any model and
makes no scheduling claim.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from cassi_field_atlas import sha256_value
from cassi_field_owner import FieldIntelligenceOwner

from run_cassi_reasoning_scenario import (
    stage_five,
    stage_four,
    stage_one,
    stage_seven,
    stage_six,
    stage_three,
    stage_two,
    task_state,
    world,
)

SCHEMA = "cassifi.packet-trace-check.v1"


def scheduler_payloads(task: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every episode payload in the task state that carries a scheduler trace."""

    found: list[dict[str, Any]] = []
    records = task.get("records")
    if not isinstance(records, Mapping):
        return found
    for identity, versions in records.items():
        if not isinstance(versions, list):
            continue
        for version in versions:
            payload = (
                version.get("payload") if isinstance(version, Mapping) else None
            )
            if not isinstance(payload, Mapping):
                continue
            scheduler = payload.get("scheduler")
            if isinstance(scheduler, Mapping) and isinstance(
                scheduler.get("snapshots"), list
            ):
                found.append(
                    {
                        "record_id": str(identity),
                        "episode_id": payload.get("episode_id"),
                        "phase": payload.get("phase"),
                        "scheduler": dict(scheduler),
                    }
                )
    return found


def verify_snapshot(row: Mapping[str, Any]) -> tuple[bool, str]:
    stored = row.get("snapshot_sha256")
    body = {key: value for key, value in row.items() if key != "snapshot_sha256"}
    computed = sha256_value(body)
    return (isinstance(stored, str) and stored == computed), computed


def describe(row: Mapping[str, Any]) -> dict[str, Any]:
    details = row.get("selected_score_details") or {}
    cue = details.get("cue") if isinstance(details, Mapping) else None
    valid, computed = verify_snapshot(row)
    return {
        "dispatch": row.get("dispatch"),
        "eligible_count": len(row.get("eligible") or []),
        "reason": row.get("reason"),
        "selected": row.get("selected"),
        "selected_score": row.get("selected_score"),
        "selected_source_binding": row.get("selected_source_binding"),
        "selected_support": row.get("selected_support"),
        "base_priority": details.get("base_priority")
        if isinstance(details, Mapping)
        else None,
        "cue_kind": cue.get("kind") if isinstance(cue, Mapping) else None,
        "cue_activation": cue.get("activation") if isinstance(cue, Mapping) else None,
        "cue_source_state_sha256": cue.get("source_state_sha256")
        if isinstance(cue, Mapping)
        else None,
        "snapshot_sha256_valid": valid,
        "recomputed_sha256": computed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("_diag/packet-trace-check/trace.json")
    )
    parser.add_argument("--data-home", type=Path, default=Path("_diag/packet-trace-check/owner"))
    arguments = parser.parse_args()
    home = arguments.data_home
    if home.exists():
        shutil.rmtree(home)
    home.mkdir(parents=True)

    # Snapshot the persisted arm homes BEFORE the scenario stages run: stage_four
    # removes and rewrites _diag/selection-arms/<method>, so a copy taken later
    # would only re-validate this process's own fresh output.
    staging = home / "arms-staged"
    staged: list[dict[str, Any]] = []
    for method in (
        "baseline",
        "hierarchy",
        "static",
        "live",
        "shuffled",
        "acquired",
        "source-binding",
    ):
        source = Path("_diag") / "selection-arms" / method
        if not source.exists():
            staged.append({"method": method, "present": False})
            continue
        newest = max(
            path.stat().st_mtime for path in source.rglob("*") if path.is_file()
        )
        destination = staging / method
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        staged.append(
            {
                "method": method,
                "present": True,
                "source": str(source),
                "source_newest_mtime": newest,
                "staged_at": str(destination),
                "note": "copied before this run executed the scenario",
            }
        )

    scene = world()
    with FieldIntelligenceOwner(home) as owner:
        stage_one(owner, scene)
        stage_two(owner, scene)
        stage_three(owner, scene)
        stage_four(owner, scene)
        stage_five(scene)
        stage_six(owner)
        # The source-binding arm carries the rows this check re-validates; the
        # staged copy above is the one taken before this run rewrote it.
        stage_seven(owner)
        episodes = scheduler_payloads(task_state(owner))

    traces = []
    for episode in episodes:
        rows = [describe(row) for row in episode["scheduler"]["snapshots"]]
        traces.append(
            {
                "record_id": episode["record_id"],
                "episode_id": episode["episode_id"],
                "phase": episode["phase"],
                "method": episode["scheduler"].get("method"),
                "selector": episode["scheduler"].get("selector"),
                "dispatch_count": episode["scheduler"].get("dispatch_count"),
                "rows": rows,
                "all_hashes_valid": all(row["snapshot_sha256_valid"] for row in rows),
                "cue_kinds": sorted(
                    {row["cue_kind"] for row in rows if row["cue_kind"] is not None}
                ),
            }
        )

    # The packet-strength rows live on the per-method selection arms, whose data
    # homes persist under _diag/selection-arms/<method>. Read copies so the
    # evidence trees are never touched.
    arms: list[dict[str, Any]] = []
    for staged_arm in staged:
        method = staged_arm["method"]
        if not staged_arm.get("present"):
            arms.append({"method": method, "present": False})
            continue
        copy = Path(staged_arm["staged_at"])
        provenance = {
            "source": staged_arm["source"],
            "source_newest_mtime": staged_arm["source_newest_mtime"],
        }
        try:
            with FieldIntelligenceOwner(copy) as arm_owner:
                arm_episodes = scheduler_payloads(task_state(arm_owner))
        except Exception as error:  # record, never mask
            arms.append(
                {
                    "method": method,
                    "present": True,
                    "provenance": provenance,
                    "unreadable": repr(error),
                }
            )
            continue
        arm_traces = []
        for episode in arm_episodes:
            rows = [describe(row) for row in episode["scheduler"]["snapshots"]]
            arm_traces.append(
                {
                    "episode_id": episode["episode_id"],
                    "scheduler_method": episode["scheduler"].get("method"),
                    "rows": rows,
                    "all_hashes_valid": all(row["snapshot_sha256_valid"] for row in rows),
                }
            )
        arms.append(
            {
                "method": method,
                "present": True,
                "provenance": provenance,
                "episodes": arm_traces,
                "rows_with_cue_activation": sum(
                    1
                    for trace in arm_traces
                    for row in trace["rows"]
                    if row["cue_activation"] is not None
                ),
                "all_hashes_valid": all(
                    trace["all_hashes_valid"] for trace in arm_traces
                ),
                "rows_with_source_binding": sum(
                    1
                    for trace in arm_traces
                    for row in trace["rows"]
                    if row["selected_source_binding"] is not None
                ),
            }
        )

    control_source = None
    control_changed = None
    for episode in episodes:
        for row in episode["scheduler"]["snapshots"]:
            body = {key: value for key, value in row.items() if key != "snapshot_sha256"}
            mutated = dict(body)
            mutated["selected"] = f"{mutated.get('selected')}-mutated"
            control_source = row.get("snapshot_sha256")
            control_changed = sha256_value(mutated) != control_source
            break
        if control_source is not None:
            break

    receipt = {
        "schema": SCHEMA,
        "episodes": traces,
        "summary": {
            "episodes": len(traces),
            "total_dispatches": sum(len(trace["rows"]) for trace in traces),
            "episodes_with_all_hashes_valid": sum(
                1 for trace in traces if trace["all_hashes_valid"]
            ),
            "methods": sorted({trace["method"] for trace in traces if trace["method"]}),
            "cue_kinds": sorted(
                {kind for trace in traces for kind in trace["cue_kinds"]}
            ),
            "rows_with_cue_activation": sum(
                1
                for trace in traces
                for row in trace["rows"]
                if row["cue_activation"] is not None
            ),
            "arm_homes_present": [
                arm["method"] for arm in arms if arm.get("present")
            ],
            "arm_rows_with_cue_activation": sum(
                int(arm.get("rows_with_cue_activation") or 0) for arm in arms
            ),
            "arm_rows_with_source_binding": sum(
                int(arm.get("rows_with_source_binding") or 0) for arm in arms
            ),
            "arm_all_hashes_valid": all(
                bool(arm.get("all_hashes_valid"))
                for arm in arms
                if arm.get("present")
            ),
        },
        "selection_arms": arms,
        "control": {
            "mutating_selected_changes_the_digest": control_changed,
            "source_digest": control_source,
        },
        "reading": {
            "trace_is_addressable": bool(traces),
            "every_row_hash_valid": all(trace["all_hashes_valid"] for trace in traces)
            if traces
            else False,
            "priority_is_not_activation": (
                "selected_score is a scheduler priority; per-dispatch packet "
                "strength appears only as cue_activation for methods that carry one"
            ),
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(receipt["summary"], indent=1, sort_keys=True))
    print(json.dumps(receipt["control"], indent=1, sort_keys=True))
    print(f"receipt: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
