from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def verify(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("boundary run result must be an object")
    if result.get("schema") != "cassi.qi-flow-boundaries-run.v1":
        raise ValueError("boundary run schema mismatch")
    if result.get("status") != "PASS":
        raise ValueError("boundary run did not pass")
    required = (
        "clock_schedule_sha256",
        "clock_lcm_denominator",
        "clock_ticks_per_world_tick",
        "packet_event_id",
        "journal_entry_frame_sha256",
        "journal_entry_head_sha256",
        "journal_replay_count",
        "commit_sha256",
        "commit_event_id",
        "acknowledgement_sha256",
        "watermark_sequence",
        "passive_egress",
    )
    missing = [name for name in required if name not in result]
    if missing:
        raise ValueError(f"boundary run result omits {missing!r}")
    for name in (
        "clock_schedule_sha256",
        "journal_entry_frame_sha256",
        "journal_entry_head_sha256",
        "commit_sha256",
        "acknowledgement_sha256",
    ):
        value = result[name]
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            raise ValueError(f"{name} is not a lowercase SHA-256 digest")
    if result["clock_lcm_denominator"] != 6 or result["clock_ticks_per_world_tick"] != 6:
        raise ValueError("clock LCM/tick evidence is inconsistent")
    if result["journal_replay_count"] != 1 or result["watermark_sequence"] != 0:
        raise ValueError("journal replay or watermark evidence is inconsistent")
    if result["packet_event_id"] != result["commit_event_id"]:
        raise ValueError("Commit A event identity does not match packet")
    egress = result["passive_egress"]
    if not isinstance(egress, Mapping) or egress.get("committed") is not True:
        raise ValueError("passive egress was not committed")
    if egress.get("no_time_advancement") is not True:
        raise ValueError("passive egress advanced logical time")
    residual = egress.get("residual")
    if (
        isinstance(residual, bool)
        or not isinstance(residual, (int, float))
        or not math.isfinite(float(residual))
        or abs(float(residual)) > 2.0e-12
    ):
        raise ValueError("passive egress work closure failed")
    return {"status": "PASS", "checks": len(required) + 5}


def verify_path(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return verify(value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify focused W7 boundary evidence")
    parser.add_argument("path", nargs="?", default="_diag/cassi_qi_boundaries.json")
    args = parser.parse_args()
    print(json.dumps(verify_path(args.path), sort_keys=True))
