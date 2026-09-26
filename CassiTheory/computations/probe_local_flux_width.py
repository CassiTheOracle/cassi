"""A localized member of the flux-width family: does it saturate in span?

The flat flux width is a family indexed by its patch, and the span curve of
`computations/probe_flux_width_span.py` shows no member saturates: a growing patch
eventually folds in the neighbouring tubes' counter-flux.  This probe measures a
localized member of the same family, the co-signed flux

    Gamma_loc = int_P max(s . omega.N, 0) dA,   s = sign(omega.omega0.N),

which keeps exactly the flux that shares the tube's own sign at the tracer.  The
counter-sign part is excluded rather than cancelled, so the reading stops growing
once the patch covers the tube.  Two things are measured per span: whether the
deviation of log a_loc from the inviscid law saturates, and whether the local
member obeys the width law (22) of `turbulence/navier-stokes-tube-curvature-coherence.md`.

Exploratory: this characterizes the measured object, it does not test a frozen
protocol.

Usage:
    python computations/probe_local_flux_width.py [--family helix_wide] [--spans 4,6,8,10]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def both_fluxes(probe, state, position, patch, order: int) -> dict[str, float]:
    """Flat and co-signed fluxes through one patch, in a single quadrature pass.

    Both readings share the nodes and the weights, so the difference between them
    is the counter-sign part of the patch alone.
    """
    cross = np.cross(patch[0], patch[1])
    area = float(np.linalg.norm(cross))
    normal = cross / max(area, 1e-300)
    rows = probe.flux_rows()
    nodes, weights = _quadrature(order)
    centre = probe.evaluate_rows(rows, state, position)
    omega = np.asarray(centre[0:3])
    sign = 1.0 if float(np.dot(omega, normal)) >= 0.0 else -1.0
    # The core reading of the viscous ratio, w . Dw / |w|^2, at the tracer.
    core_ratio = float(np.dot(omega, np.asarray(centre[3:6]))) / max(
        float(np.dot(omega, omega)), 1e-300
    )

    flat = laplacian = local = local_laplacian = 0.0
    for left, left_weight in zip(nodes, weights):
        for right, right_weight in zip(nodes, weights):
            offset = (left - 0.5) * patch[0] + (right - 0.5) * patch[1]
            readings = probe.evaluate_rows(rows, state, position + offset)
            through = float(np.dot(np.asarray(readings[0:3]), normal))
            lap_through = float(np.dot(np.asarray(readings[3:6]), normal))
            weight = left_weight * right_weight
            flat += weight * through
            laplacian += weight * lap_through
            if sign * through > 0.0:
                local += weight * through
                local_laplacian += weight * lap_through
    return {
        "area": area,
        "flux": area * flat,
        "laplacian_flux": area * laplacian,
        "local_flux": area * local,
        "local_laplacian_flux": area * local_laplacian,
        "core_ratio": core_ratio,
        "masked_share": (local / flat) if abs(flat) > 1e-300 else float("nan"),
        "sign": sign,
    }


def _quadrature(order: int):
    spec = importlib.util.spec_from_file_location(
        "fluxwidth", ROOT / "computations" / "navier_stokes_flux_width.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.quadrature_nodes(order)


def carry(fw, depletion, long_trajectory, family: str, span_factor: float, order: int, stride: int) -> dict[str, Any]:
    """Carry the tracer and patch, reading the flat and the localized widths."""
    box = long_trajectory.TorchGalerkinBox(fw.CUTOFF, fw.GRID_FACTOR * fw.CUTOFF + 1)
    probe = fw.FrameProbe(box)
    record_case = next(item for item in depletion.CASES if item["name"] == family)
    state, _ = depletion.initial_state(record_case, box)
    dt = fw.HORIZON / float(fw.STEPS)
    position, direction, first, second, core_width = fw.release(box, probe, state)
    patch_side = span_factor * core_width
    patch = [patch_side * first, patch_side * second]
    rhs = box.right_hand_side(state)

    rows: list[dict[str, float]] = []

    def record(index: int) -> None:
        row = fw.sample(probe, box, state, position, patch, fw.NU, order)
        fluxes = both_fluxes(probe, state, position, patch, order)
        magnitude = max(float(row["magnitude"]), 1e-300)
        row["time"] = float(index * dt)
        row["local_width"] = math.sqrt(
            max(fluxes["local_flux"], 1e-300) / (math.pi * magnitude)
        )
        row["local_spread"] = 0.5 * fw.NU * (
            fluxes["local_laplacian_flux"] / max(fluxes["local_flux"], 1e-300)
            - fluxes["core_ratio"]
        )
        row["masked_share"] = fluxes["masked_share"]
        rows.append(row)

    record(0)
    for index in range(fw.STEPS):
        state, position, patch = fw.advance(probe, box, state, rhs, dt, position, patch)
        rhs = box.right_hand_side(state)
        if (index + 1) % stride == 0:
            record(index + 1)

    axial = sum(
        0.5 * (earlier["axial"] + later["axial"]) * (later["time"] - earlier["time"])
        for earlier, later in zip(rows, rows[1:])
    )
    local_change = math.log(rows[-1]["local_width"] / rows[0]["local_width"])
    flat_width_change = math.log(rows[-1]["width"] / rows[0]["width"])
    spread = sum(
        0.5 * (earlier["local_spread"] + later["local_spread"])
        * (later["time"] - earlier["time"])
        for earlier, later in zip(rows, rows[1:])
    )
    return {
        "span": span_factor,
        "core_width": core_width,
        "patch_side": patch_side,
        "local_width_start": rows[0]["local_width"],
        "local_width_end": rows[-1]["local_width"],
        "masked_share_start": rows[0]["masked_share"],
        "masked_share_end": rows[-1]["masked_share"],
        "flat_deviation": flat_width_change + 0.5 * axial,
        "local_deviation": local_change + 0.5 * axial,
        "local_spread": spread,
        "local_removed": local_change + 0.5 * axial - spread,
        "axial": axial,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="helix_wide")
    parser.add_argument("--spans", default="4,6,8,10")
    parser.add_argument("--order", type=int, default=6)
    parser.add_argument("--stride", type=int, default=4)
    arguments = parser.parse_args()

    fw = load_module(ROOT / "computations" / "navier_stokes_flux_width.py")
    long_trajectory = load_module(
        ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
    )
    depletion = load_module(
        ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
    )

    readings = []
    for span in (float(value) for value in arguments.spans.split(",")):
        entry = carry(fw, depletion, long_trajectory, arguments.family, span, arguments.order, arguments.stride)
        readings.append(entry)
        print(
            f"span {span:5.1f}  side {entry['patch_side']:.4f}  "
            f"flat {entry['flat_deviation']:+.4e}  "
            f"local {entry['local_deviation']:+.4e}  "
            f"spread {entry['local_spread']:+.4e}  "
            f"removed {entry['local_removed']:+.3e}  "
            f"masked {entry['masked_share_start']:.3f}->{entry['masked_share_end']:.3f}"
        )

    flat = [entry["flat_deviation"] for entry in readings]
    local = [entry["local_deviation"] for entry in readings]
    flat_move = max(
        abs(b - a) / max(abs(a), 1e-300) for a, b in zip(flat, flat[1:])
    ) if len(flat) > 1 else float("nan")
    local_move = max(
        abs(b - a) / max(abs(a), 1e-300) for a, b in zip(local, local[1:])
    ) if len(local) > 1 else float("nan")
    print("=" * 78)
    print(f"flat largest relative move {flat_move:.3f}; localized largest {local_move:.3f}")
    print(
        "saturates"
        if local_move < 0.05
        else "does not saturate over the declared spans"
    )
    print(json.dumps({"family": arguments.family, "readings": readings}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
