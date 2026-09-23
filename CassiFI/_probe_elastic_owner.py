"""Operational check: the owner's elastic resource surface, live and reopened.

Exercises the real owner entry point (operate_computer) for the declared
resource policy, placement, tier accounting, policy enforcement on growth, and
restart continuity.  Prints one compact JSON line per step.
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile

from cassi_field_owner import FieldIntelligenceOwner

PAGED = os.environ.get("ELASTIC_PAGED", "1") == "1"
PLACE = PAGED and os.environ.get("ELASTIC_PLACE", "1") == "1"


def _membrane_profile() -> dict:
    """The regional profile the owner can create and page.

    A neural-membrane computer is produced by converting an existing field
    (regions' enable_neural_membrane), not by initial construction, so the
    owner-created computer here is a plain regional one.
    """

    from cassi_learning_computer import _regional_profile

    profile, _scalar = _regional_profile(
        {"stack_capacity": 32, "max_steps": 32}, max_field_bytes=64 * 1024 * 1024
    )
    return profile.as_dict()

ROOT = pathlib.Path(tempfile.mkdtemp(prefix="elastic-owner-"))
LIMITS = {
    "max_logical_bytes": 64 * 1024 * 1024,
    "ram_bytes": 32 * 1024 * 1024,
    "vram_bytes": 16 * 1024 * 1024,
    "storage_bytes": 512 * 1024 * 1024,
    "device": "cpu",
}


def show(tag: str, value: object) -> None:
    print(tag, json.dumps(value, sort_keys=True, default=str)[:700], flush=True)


def call(owner, identity, action, **arguments):
    return owner.operate_computer(
        identity, computer_id="main", action=action, arguments=arguments or None
    )


with FieldIntelligenceOwner(ROOT) as owner:
    configured = call(
        owner,
        "configure",
        "configure",
        profile=_membrane_profile(),
        **({"resident_pages": 8} if PAGED else {}),
        resource_limits=LIMITS,
    )
    row = owner.state.computers[0]
    show(
        "CONFIGURE",
        {
            "paged": row.is_paged,
            "nbytes": row.nbytes,
            "limits": configured["receipt"]["resource_limits"],
            "resident_limit": row.resident_limit,
        },
    )

    show("RESOURCES-READ", call(owner, "resources-read", "resources")["receipt"])
    measured = call(owner, "resources-measured", "resources")["receipt"]
    live = owner.computer_resources("main")
    show(
        "RESOURCES-MEASURED",
        {
            "live_resources": None if live["resources"] is None else sorted(live["resources"]),
            "live_tiers": None if live["resources"] is None else live["resources"].get("tiers"),
            "paged": measured["paged"],
            "residency_keys": sorted((live["residency"] or {}).keys()),
        },
    )

    if PLACE:
        show("PLACE-RAM", call(owner, "place-ram", "place", pages=[0, 1], tier="ram")["receipt"])
        try:
            show("PLACE-STORAGE", call(owner, "place-storage", "place", pages=[0, 1], tier="storage")["receipt"])
        except Exception as exc:  # noqa: BLE001 - report the tier's real behaviour
            show("PLACE-STORAGE", f"{type(exc).__name__}: {exc}")
        try:
            call(owner, "place-vram-denied", "place", pages=[0], tier="vram")
            show("PLACE-VRAM-DENIED", "unexpectedly allowed")
        except Exception as exc:  # noqa: BLE001 - the refusal is the check
            show("PLACE-VRAM-DENIED", f"{type(exc).__name__}: {exc}")

    updated = call(
        owner,
        "resources-update",
        "resources",
        limits={**LIMITS, "device": "cuda", "vram_bytes": 256 * 1024 * 1024},
    )["receipt"]
    show("RESOURCES-UPDATE", updated["resource_limits"])

    if PLACE:
        try:
            call(owner, "place-vram-allowed", "place", pages=[0], tier="vram")
            show("PLACE-VRAM-ALLOWED", "accepted")
        except Exception as exc:  # noqa: BLE001 - report what the tier does
            show("PLACE-VRAM-ALLOWED", f"{type(exc).__name__}: {exc}")

    try:
        call(owner, "grow-refused", "grow", stack_capacity=1_000_000)
        show("GROW-REFUSED", "unexpectedly allowed")
    except Exception as exc:  # noqa: BLE001 - the refusal is the check
        show("GROW-REFUSED", f"{type(exc).__name__}: {exc}")

    grown = call(owner, "grow-allowed", "grow", stack_capacity=64)
    show("GROW-ALLOWED", {"nbytes": owner.state.computers[0].nbytes, "status": grown["receipt"].get("status")})
    show("STATE", {"computers": len(owner.state.computers), "generation": owner.state.generation})

with FieldIntelligenceOwner(ROOT) as reopened:
    row = reopened.state.computers[0]
    image = getattr(row.field, "image", None)
    objects_on_disk = sorted(p.name for p in (ROOT / "objects").glob("*")) if (ROOT / "objects").exists() else []
    show(
        "REOPEN",
        {
            "paged": row.is_paged,
            "nbytes": row.nbytes,
            "policy": reopened.computer_resources("main")["resource_limits"],
            "device": reopened.computer_resources("main")["device"],
            "manager_bound": getattr(image, "resource_manager", None) is not None,
            "object_files_on_disk": len(objects_on_disk),
            "residency_limits": (row.residency().get("resource_limits") if row.residency() else None),
        },
    )
    if PLACE:
        show("REOPEN-PLACE", call(reopened, "place-after-restart", "place", pages=[2], tier="ram")["receipt"])
