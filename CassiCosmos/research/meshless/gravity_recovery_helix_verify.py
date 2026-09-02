#!/usr/bin/env python
"""Evaluate the frozen G65 live spatial-winding eligibility gate."""

import base64
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np

from verify_topology_observatory import (  # pyright: ignore[reportMissingImports]
    TAU,
    _plaquette_windings,
    detect,
)


def _field(payload: str, grid_n: int) -> np.ndarray:
    values = np.frombuffer(base64.b64decode(payload), dtype=np.float32)
    expected = grid_n**3
    if values.size != expected:
        raise ValueError(f"field has {values.size} values; expected {expected}")
    return values.reshape((grid_n, grid_n, grid_n)).astype(np.float64)


def _closure_residual(theta: np.ndarray) -> float:
    edges, windings = _plaquette_windings(theta)
    dx, dy, dz = edges["x"], edges["y"], edges["z"]
    circulations = {
        "xy": dx[:, :-1, :] + dy[1:, :, :] - dx[:, 1:, :] - dy[:-1, :, :],
        "yz": dy[:, :, :-1] + dz[:, 1:, :] - dy[:, :, 1:] - dz[:, :-1, :],
        "zx": dz[:-1, :, :] + dx[:, :, 1:] - dz[1:, :, :] - dx[:, :, :-1],
    }
    return max(
        float(np.max(np.abs(circulations[name] / TAU - windings[name])))
        for name in ("xy", "yz", "zx")
    )


def main() -> None:
    source = Path(
        sys.argv[1] if len(sys.argv) > 1 else "_diag/gravity_recovery_helix_gpu.json"
    )
    data = json.loads(source.read_text(encoding="utf-8"))
    grid_n = int(data["grid_N"])
    snapshots = data["snapshots"]
    if [int(snapshot["step"]) for snapshot in snapshots] != [32, 33, 34]:
        raise ValueError("registered snapshots must be steps 32, 33, and 34")

    rows = []
    for snapshot in snapshots:
        ey = _field(snapshot["ey_b64"], grid_n)
        ei = _field(snapshot["ei_b64"], grid_n)
        detection = detect(ey, ei)
        rings = sum(
            int(component["closed"])
            for component in detection.metrics["components"]
        )
        winding_fraction = detection.metrics["nonzero_plaquettes"] / float(
            3 * grid_n**3
        )
        closure_residual = _closure_residual(detection.theta)
        finite = bool(
            np.isfinite(ey).all()
            and np.isfinite(ei).all()
            and math.isfinite(winding_fraction)
            and math.isfinite(closure_residual)
        )
        passed = bool(
            finite
            and detection.metrics["phase_valid"]
            and rings >= 3
            and winding_fraction >= 0.05
            and closure_residual <= 1e-5
        )
        row = {
            "step": int(snapshot["step"]),
            "phase_valid": bool(detection.metrics["phase_valid"]),
            "amplitude_min": float(detection.metrics["amplitude_min"]),
            "nonzero_plaquettes": int(detection.metrics["nonzero_plaquettes"]),
            "component_count": int(detection.metrics["component_count"]),
            "rings": rings,
            "winding_fraction": winding_fraction,
            "closure_residual": closure_residual,
            "finite": finite,
            "pass": passed,
        }
        rows.append(row)
        print(
            "step=%d rings=%d winding_fraction=%.9f closure_residual=%.3e "
            "phase_valid=%s finite=%s => %s"
            % (
                row["step"],
                rings,
                winding_fraction,
                closure_residual,
                row["phase_valid"],
                finite,
                "PASS" if passed else "FAIL",
            )
        )

    g65 = len(rows) == 3 and all(row["pass"] for row in rows)
    result = {
        "source": str(source),
        "tree_full_builds": int(data["full_builds"]),
        "tree_hierarchical_refits": int(data["hierarchical_refits"]),
        "tree_transition_full_builds": int(data["transition_full_builds"]),
        "snapshots": rows,
        "G65": "PASS" if g65 else "FAIL",
        "G66": "ELIGIBLE" if g65 else "STOPPED",
    }
    Path("_diag/gravity_recovery_helix_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print("G65: %s" % result["G65"])
    print("G66: %s" % result["G66"])
    raise SystemExit(0 if g65 else 1)


if __name__ == "__main__":
    main()
