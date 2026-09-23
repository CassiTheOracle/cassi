"""Operational check: bounded paged execution and automatic residency growth.

Runs the same real program on a dense computer and on a paged computer whose
page allowance is one page, then on a paged computer whose declared RAM budget
cannot admit the pages the program needs.  Prints one compact JSON line per
step.
"""

from __future__ import annotations

import json
import pathlib
import tempfile

import cassi_field_computer as computer_module
from cassi_field_owner import FieldIntelligenceOwner
from cassi_learning_computer import _regional_profile

ROOT = pathlib.Path(tempfile.mkdtemp(prefix="elastic-execution-"))
CLAUSES = tuple((index + 1,) for index in range(120))
FRAME = computer_module.propagation_workspace(CLAUSES, variable_count=120)
PUSHES = tuple(
    (computer_module.PUSH, 0, value, pc + 1, 0) for pc, value in enumerate(FRAME)
)
ENTRY = len(PUSHES)
PROGRAM = PUSHES + (
    (computer_module.PROPAGATE, 0, ENTRY + 1, 0, 0),
    (computer_module.BRANCH, computer_module.PROPAGATION_PROGRESS, ENTRY, ENTRY + 2, 0),
    (computer_module.PUSH_ACC, 1, ENTRY + 3, 0, 0),
    (computer_module.HALT, 0, 0, 0, 0),
)
STEPS = 4096


def show(tag: str, value: object) -> None:
    print(tag, json.dumps(value, sort_keys=True, default=str)[:700], flush=True)


def call(owner, identity, computer_id, action, **arguments):
    return owner.operate_computer(
        identity, computer_id=computer_id, action=action, arguments=arguments or None
    )


def profile() -> dict:
    return {"program_capacity": len(PROGRAM), "stack_capacity": len(FRAME), "max_steps": 4096}


def task(owner, computer_id):
    row = next(item for item in owner.state.computers if item.computer_id == computer_id)
    inspected = row.inspect()
    return {
        "status": inspected["task"]["status"],
        "left": inspected["task"].get("left"),
        "paged": row.is_paged,
        "nbytes": row.nbytes,
    }


def policy(**overrides) -> dict:
    base = {
        "max_logical_bytes": 64 * 1024 * 1024,
        "ram_bytes": 32 * 1024 * 1024,
        "vram_bytes": 16 * 1024 * 1024,
        "device": "cpu",
    }
    base.update(overrides)
    return base


with FieldIntelligenceOwner(ROOT) as owner:
    call(
        owner, "cfg-dense", "dense", "configure",
        profile=profile(), resource_limits=policy(),
    )
    call(owner, "load-dense", "dense", "load", program=PROGRAM, left=FRAME)
    dense_run = call(owner, "run-dense", "dense", "advance", steps=STEPS)
    dense_task = task(owner, "dense")
    show(
        "DENSE-ADVANCE",
        {
            "transitions_executed": dense_run["receipt"].get("transitions_executed"),
            "status": dense_run["receipt"].get("status"),
            "paused": dense_run["receipt"].get("paused"),
        },
    )

    paged_cfg = call(
        owner, "cfg-paged", "main", "configure",
        profile=profile(), resident_pages=2, resource_limits=policy(),
    )
    show("PAGED-ADOPT", paged_cfg["receipt"].get("residency_decision"))
    before = owner.computer_resources("main")
    show(
        "PAGED-START",
        {
            "resident_limit": (before["residency"] or {}).get("resident_limit"),
            "page_count": (before["residency"] or {}).get("page_count"),
            "logical_bytes": before["logical_bytes"],
            "ram_bytes": before["resource_limits"]["ram_bytes"],
        },
    )
    call(owner, "load-paged", "main", "load", program=PROGRAM, left=FRAME)
    try:
        advanced = call(owner, "run-paged", "main", "advance", steps=STEPS)
        receipt = advanced["receipt"]
        show(
            "PAGED-ADVANCE",
            {
                "transitions_executed": receipt.get("transitions_executed"),
                "status": receipt.get("status"),
                "paused": receipt.get("paused"),
                "reason": receipt.get("reason"),
                "residency_decision": receipt.get("residency_decision"),
            },
        )
    except Exception as exc:  # noqa: BLE001 - the refusal is a finding
        show("PAGED-ADVANCE", f"{type(exc).__name__}: {exc}")

    paged_task = task(owner, "main")
    after = owner.computer_resources("main")
    show(
        "PAGED-END",
        {
            "task": paged_task,
            "resident_limit": (after["residency"] or {}).get("resident_limit"),
            "residency": (after["residency"] or {}).get("residency"),
            "used_bytes": (after["resources"] or {}).get("used_bytes"),
            "high_water_bytes": (after["resources"] or {}).get("high_water_bytes"),
        "resident_high_water_pages": (after["residency"] or {}).get("resident_high_water_pages"),
            "wait_count": (after["resources"] or {}).get("wait_count"),
            "ram_bytes": after["resource_limits"]["ram_bytes"],
        },
    )
    show(
        "AGREEMENT",
        {
            "equal": dense_task == paged_task,
            "dense_status": dense_task.get("status"),
            "paged_status": paged_task.get("status"),
            "dense_left_sha": __import__("hashlib").sha256(
                repr(dense_task.get("left")).encode()
            ).hexdigest()[:16],
            "paged_left_sha": __import__("hashlib").sha256(
                repr(paged_task.get("left")).encode()
            ).hexdigest()[:16],
            "dense_right": dense_task.get("right"),
            "paged_right": paged_task.get("right"),
        },
    )

    try:
        call(
            owner, "cfg-tight", "tight", "configure",
            profile=profile(), resident_pages=2,
            resource_limits=policy(ram_bytes=200_000),
        )
        call(owner, "load-tight", "tight", "load", program=PROGRAM, left=FRAME)
        result = call(owner, "run-tight", "tight", "advance", steps=STEPS)
        show(
            "TIGHT-BUDGET",
            {
                "residency_decision": result["receipt"].get("residency_decision"),
                "stop": result["receipt"].get("stop"),
            },
        )
    except Exception as exc:  # noqa: BLE001 - the refusal is the finding
        show("TIGHT-BUDGET", f"{type(exc).__name__}: {exc}")

    differing = sorted(
        key
        for key in set(dense_task) | set(paged_task)
        if dense_task.get(key) != paged_task.get(key)
    )
    verdict = {
        "dense_equals_paged": (
            dense_task.get("status") == paged_task.get("status")
            and repr(dense_task.get("left")) == repr(paged_task.get("left"))
            and dense_task.get("right") == paged_task.get("right")
        ),
        "differing_keys": differing,
        "paged_task": paged_task,
        "resident_limit_after": (after["residency"] or {}).get("resident_limit"),
        "page_count": (after["residency"] or {}).get("page_count"),
        "used_bytes": (after["resources"] or {}).get("used_bytes"),
        "high_water_bytes": (after["resources"] or {}).get("high_water_bytes"),
        "resident_high_water_pages": (after["residency"] or {}).get("resident_high_water_pages"),
        "ram_bytes": after["resource_limits"]["ram_bytes"],
        "within_budget": ((after["resources"] or {}).get("high_water_bytes") or {}).get("ram", 0)
        <= after["resource_limits"]["ram_bytes"],
        "wait_count": (after["resources"] or {}).get("wait_count"),
        "resource_keys": sorted((after["resources"] or {}).keys()),
        "page_stats": (after["residency"] or {}).get("statistics")
        or (after["resources"] or {}).get("kind_high_water_bytes"),
    }
    show("VERDICT", verdict)
    print("FAIL" if not verdict["dense_equals_paged"] or not verdict["within_budget"] else "PASS")
