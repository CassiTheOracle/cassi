from __future__ import annotations

import argparse
import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Mapping

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _finite_value(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
    elif isinstance(value, str) and re.fullmatch(r"f64:[0-9a-f]{16}", value):
        result = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
    else:
        raise ValueError("work enclosure value is not finite")
    if not math.isfinite(result):
        raise ValueError("work enclosure value is not finite")
    return result


def verify(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise ValueError("permeability run result must be an object")
    if result.get("status") != "PASS":
        raise ValueError("permeability run did not pass")
    required = (
        "profile_sha256",
        "descriptor_sha256",
        "live_admitted_work",
        "frozen_admitted_work",
        "receipt_sha256",
        "openness_receipt_sha256",
        "zero_work_rejected",
    )
    missing = [name for name in required if name not in result]
    if missing:
        raise ValueError(f"permeability run result omits {missing!r}")
    for name in ("profile_sha256", "descriptor_sha256", "receipt_sha256", "openness_receipt_sha256"):
        value = result[name]
        if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
            raise ValueError(f"{name} is not a lowercase SHA-256 digest")
    for name in ("live_admitted_work", "frozen_admitted_work"):
        value = result[name]
        try:
            upper = _finite_value(value.get("upper", 0.0)) if isinstance(value, Mapping) else 0.0
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name} is not positive admitted work") from exc
        if not isinstance(value, Mapping) or upper <= 0.0:
            raise ValueError(f"{name} is not positive admitted work")
    if result["zero_work_rejected"] is not True:
        raise ValueError("zero incident work was not rejected")
    return {"status": "PASS", "checks": len(required) + 3}


def verify_path(path: str | Path) -> dict[str, Any]:
    return verify(json.loads(Path(path).read_text(encoding="utf-8")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify focused W7P permeability evidence")
    parser.add_argument("path", nargs="?", default="_diag/cassi_qi_boundary_permeability.json")
    args = parser.parse_args()
    print(json.dumps(verify_path(args.path), sort_keys=True))
