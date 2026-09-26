"""Span dependence of the flux-based tube width, on the retained families.

Exploratory: this probe characterizes the measured object, it does not test a
frozen protocol.  It carries the same tracer and the same material patch geometry
as `computations/navier_stokes_flux_width.py` at several release spans, so that the
width's own dependence on the patch that reads it is measured rather than assumed.
The output is the width deviation from the inviscid law and the share of it that
the viscous profile spread accounts for, per span.

Usage:
    python computations/probe_flux_width_span.py [--family helix_wide] [--spans 3,4,5,6,8,10]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="helix_wide")
    parser.add_argument("--spans", default="3,4,5,6,8,10")
    arguments = parser.parse_args()
    spans = [float(value) for value in arguments.spans.split(",")]

    flux_width = load_module(ROOT / "computations" / "navier_stokes_flux_width.py")
    clock = load_module(ROOT / "computations" / "navier_stokes_curvature_clock.py")
    budget = load_module(ROOT / "computations" / "navier_stokes_curvature_budget.py")
    long_trajectory = load_module(
        ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
    )
    depletion = load_module(
        ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
    )

    readings: list[dict[str, Any]] = []
    for span in spans:
        entry = flux_width.integrate_case(
            clock,
            budget,
            long_trajectory,
            depletion,
            arguments.family,
            span,
            flux_width.QUADRATURE_ORDER,
            flux_width.SAMPLE_STRIDE,
        )
        integrated = flux_width.integrate_rates(entry)
        width = integrated["width"]
        spread = integrated["spread"]
        readings.append(
            {
                "span": span,
                "core_width": entry["core_width"],
                "patch_side": entry["patch_side"],
                "width_deviation": width,
                "spread": spread,
                "spread_share": (spread / width) if width != 0.0 else float("nan"),
                "spread_removed": width - spread,
                "flux_change": integrated["flux_change"],
            }
        )
        print(
            f"span {span:5.1f}  side {entry['patch_side']:.4f}  "
            f"deviation {width:+.4e}  spread {spread:+.4e}  "
            f"share {100.0 * readings[-1]['spread_share']:6.2f}%  "
            f"removed {width - spread:+.3e}"
        )

    # A saturated span would show the deviation flattening; the probe reports the
    # largest relative move between neighbouring spans as its convergence reading.
    moves = [
        abs(later["width_deviation"] - earlier["width_deviation"])
        / max(abs(earlier["width_deviation"]), 1e-300)
        for earlier, later in zip(readings, readings[1:])
    ]
    worst = max(moves) if moves else float("nan")
    print("=" * 78)
    print(
        f"largest relative move between neighbouring spans {worst:.3f}; "
        f"the deviation at the widest span is {readings[-1]['width_deviation']:+.4e}"
    )
    print(json.dumps({"family": arguments.family, "readings": readings}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
