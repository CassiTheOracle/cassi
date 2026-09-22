"""Localized members of the flux-width family: sign-masked and distance-decaying.

The flat flux width is a family indexed by its patch, and `probe_flux_width_span.py`
shows no flat member saturates: a growing patch folds in neighbouring tubes.  Two
localized members are measured here against the same carried object.

**Sign-masked.** `Gamma_sig = int_P max(s . omega.N, 0) dA` with `s` the tube's own
sign at the tracer: it excludes counter-sign neighbours and keeps same-sign ones.

**Distance-decaying.** `Gauss = int_P exp(-r^2/2 sigma^2) omega.N dA`, with `sigma`
the released core's own Hessian width, so the tube sets the only scale and the
integrand decays faster than the patch grows.  The weight is fixed in space about
the carried tracer, so it is not a material weight and the flux lemma picks up the
pump it moves through:

    D_tau Gamma_G = int (u - u0) . grad(w) (omega.N) dA + nu int w Delta omega.N dA.

The pump is evaluated rather than absorbed, which makes the decaying member's law
testable instead of merely fitted.

Both readings are taken from one quadrature pass per sample.  Exploratory: this
characterizes the measured objects, it does not test a frozen protocol.

Usage:
    python computations/probe_decaying_flux_width.py [--family helix_wide] [--spans 4,6,8,10]
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


def member_fluxes(
    probe, state, position, patch, order: int, sigma: float, label_limit: float = 0.5
) -> dict[str, float]:
    """Flat, sign-masked and Gaussian fluxes through one patch, one pass.

    The flat and sign-masked readings cover the whole patch.  The Gaussian one is
    integrated over the label box of half-width `label_limit` about the tracer's
    label, because the weight's support is set by `sigma` and spreading Gauss nodes
    across a patch far wider than the weight under-resolves the peak.  The label box
    is fixed at release, so it stays a material sub-patch of the carried one and the
    pump term below remains exact for it.
    """
    fw = _flux_width()
    cross = np.cross(patch[0], patch[1])
    area = float(np.linalg.norm(cross))
    normal = cross / max(area, 1e-300)
    rows = probe.flux_rows()
    nodes, weights = fw.quadrature_nodes(order)
    inner = [0.5 + label_limit * (node - 0.5) for node in nodes]
    inner_weights = [weight * label_limit for weight in weights]
    centre = probe.evaluate_rows(rows, state, position)
    omega = np.asarray(centre[0:3])
    u0 = np.asarray(probe.velocity(state, position))
    sign = 1.0 if float(np.dot(omega, normal)) >= 0.0 else -1.0
    # The core reading of the viscous ratio, w . Dw / |w|^2, at the tracer.
    core_ratio = float(np.dot(omega, np.asarray(centre[3:6]))) / max(
        float(np.dot(omega, omega)), 1e-300
    )

    flat = laplacian = signed = signed_laplacian = 0.0
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
                signed += weight * through
                signed_laplacian += weight * lap_through

    gauss = gauss_laplacian = pump = 0.0
    for left, left_weight in zip(inner, inner_weights):
        for right, right_weight in zip(inner, inner_weights):
            offset = (left - 0.5) * patch[0] + (right - 0.5) * patch[1]
            point = position + offset
            readings = probe.evaluate_rows(rows, state, point)
            through = float(np.dot(np.asarray(readings[0:3]), normal))
            lap_through = float(np.dot(np.asarray(readings[3:6]), normal))
            weight = left_weight * right_weight
            decay = math.exp(-float(np.dot(offset, offset)) / (2.0 * sigma * sigma))
            gauss += weight * decay * through
            gauss_laplacian += weight * decay * lap_through
            drift = np.asarray(probe.velocity(state, point)) - u0
            pump += weight * float(np.dot(drift, -(offset / (sigma * sigma)) * decay)) * through

    return {
        "area": area,
        "label_limit": label_limit,
        "flux": area * flat,
        "laplacian_flux": area * laplacian,
        "signed_flux": area * signed,
        "signed_laplacian_flux": area * signed_laplacian,
        # inner_weights already carry label_limit once, so the sub-patch area
        # factor must not be applied again.
        "gauss_flux": area * gauss,
        "gauss_laplacian_flux": area * gauss_laplacian,
        "pump": area * pump,
        "core_ratio": core_ratio,
        "signed_share": (signed / flat) if abs(flat) > 1e-300 else float("nan"),
    }


def label_box(patch, sigma: float) -> float:
    """Label half-width whose physical half-side is 3 sigma, capped at the patch."""
    span = max(float(np.linalg.norm(patch[0])), float(np.linalg.norm(patch[1])), 1e-300)
    return float(min(0.5, 3.0 * sigma / span))


_FLUX_WIDTH = None


def _flux_width():
    global _FLUX_WIDTH
    if _FLUX_WIDTH is None:
        _FLUX_WIDTH = load_module(ROOT / "computations" / "navier_stokes_flux_width.py")
    return _FLUX_WIDTH


def carry(family: str, span_factor: float, order: int, stride: int) -> dict[str, Any]:
    fw = _flux_width()
    long_trajectory = load_module(
        ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
    )
    depletion = load_module(
        ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
    )
    box = long_trajectory.TorchGalerkinBox(fw.CUTOFF, fw.GRID_FACTOR * fw.CUTOFF + 1)
    probe = fw.FrameProbe(box)
    record_case = next(item for item in depletion.CASES if item["name"] == family)
    state, _ = depletion.initial_state(record_case, box)
    dt = fw.HORIZON / float(fw.STEPS)
    position, direction, first, second, core_width = fw.release(box, probe, state)
    patch_side = span_factor * core_width
    patch = [patch_side * first, patch_side * second]
    # Fixed at release: the Gaussian reading's material sub-box, sized to the tube.
    label_limit = label_box(patch, core_width)
    rhs = box.right_hand_side(state)

    rows: list[dict[str, Any]] = []

    def record(index: int) -> None:
        row = fw.sample(probe, box, state, position, patch, fw.NU, order)
        fluxes = member_fluxes(
            probe, state, position, patch, order, core_width, label_limit
        )
        magnitude = max(float(row["magnitude"]), 1e-300)
        row["time"] = float(index * dt)
        row["signed_width"] = math.sqrt(
            max(fluxes["signed_flux"], 1e-300) / (math.pi * magnitude)
        )
        row["signed_spread"] = 0.5 * fw.NU * (
            fluxes["signed_laplacian_flux"] / max(fluxes["signed_flux"], 1e-300)
            - fluxes["core_ratio"]
        )
        row["gauss_width"] = math.sqrt(
            max(fluxes["gauss_flux"], 1e-300) / (math.pi * magnitude)
        )
        row["gauss_channel"] = 0.5 * (
            fluxes["pump"] / max(fluxes["gauss_flux"], 1e-300)
            + fw.NU
            * (
                fluxes["gauss_laplacian_flux"] / max(fluxes["gauss_flux"], 1e-300)
                - fluxes["core_ratio"]
            )
        )
        row["signed_share"] = fluxes["signed_share"]
        # The margin carried by the patch-independent width, and its bound (21).
        row["gauss_margin"] = float(row["kappa"]) * row["gauss_width"]
        margin = max(row["gauss_margin"], 1e-300)
        row["gauss_margin_bound"] = (
            row["gauss_width"] * float(row["hessian_norm"]) / margin
            + 3.5 * float(row["gradient_norm"])
            + row["gauss_width"] * abs(2.0 * row["gauss_channel"]) / margin
        )
        rows.append(row)

    record(0)
    for index in range(fw.STEPS):
        state, position, patch = fw.advance(probe, box, state, rhs, dt, position, patch)
        rhs = box.right_hand_side(state)
        if (index + 1) % stride == 0:
            record(index + 1)

    def integral(key: str) -> float:
        return sum(
            0.5 * (earlier[key] + later[key]) * (later["time"] - earlier["time"])
            for earlier, later in zip(rows, rows[1:])
        )

    axial = integral("axial")
    deviation = lambda key: math.log(rows[-1][key] / rows[0][key]) + 0.5 * axial
    margin_change = math.log(rows[-1]["gauss_margin"] / rows[0]["gauss_margin"])
    margin_closed = integral("curvature_rate_closed") + integral("gauss_channel")
    fd_rates = [
        math.log(later["gauss_margin"] / earlier["gauss_margin"])
        / max(later["time"] - earlier["time"], 1e-300)
        for earlier, later in zip(rows, rows[1:])
    ]
    worst_ratio = max(
        abs(rate) / max(0.5 * (earlier["gauss_margin_bound"] + later["gauss_margin_bound"]), 1e-300)
        for rate, earlier, later in zip(fd_rates, rows, rows[1:])
    )
    return {
        "span": span_factor,
        "core_width": core_width,
        "patch_side": patch_side,
        "sigma": core_width,
        "label_limit": label_limit,
        "gauss_half_side": label_limit * patch_side,
        "gauss_half_over_sigma": label_limit * patch_side / max(core_width, 1e-300),
        "flat_deviation": deviation("width"),
        "flat_spread": integral("spread"),
        "signed_deviation": deviation("signed_width"),
        "signed_spread": integral("signed_spread"),
        "signed_removed": deviation("signed_width") - integral("signed_spread"),
        "gauss_deviation": deviation("gauss_width"),
        "gauss_channel": integral("gauss_channel"),
        "gauss_removed": deviation("gauss_width") - integral("gauss_channel"),
        "signed_share": rows[0]["signed_share"],
        "margin_start": rows[0]["gauss_margin"],
        "margin_end": rows[-1]["gauss_margin"],
        "margin_change": margin_change,
        "margin_closed": margin_closed,
        "margin_residual": abs(margin_change - margin_closed),
        "margin_bound_ratio": worst_ratio,
        "gauss_start": rows[0]["gauss_width"],
        "gauss_end": rows[-1]["gauss_width"],
    }


def worst_move(values: list[float]) -> float:
    if len(values) < 2:
        return float("nan")
    return max(abs(b - a) / max(abs(a), 1e-300) for a, b in zip(values, values[1:]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", default="helix_wide")
    parser.add_argument("--spans", default="4,6,8,10")
    parser.add_argument("--order", type=int, default=10)
    parser.add_argument("--stride", type=int, default=4)
    arguments = parser.parse_args()

    readings = [
        carry(arguments.family, float(span), arguments.order, arguments.stride)
        for span in arguments.spans.split(",")
    ]
    for entry in readings:
        print(
            f"span {entry['span']:5.1f}  side {entry['patch_side']:.4f}  "
            f"sigma {entry['sigma']:.4f}  flat {entry['flat_deviation']:+.4e}  "
            f"signed {entry['signed_deviation']:+.4e}  "
            f"gauss {entry['gauss_deviation']:+.4e}  "
            f"gauss removed {entry['gauss_removed']:+.3e}"
        )

    flat_move = worst_move([entry["flat_deviation"] for entry in readings])
    signed_move = worst_move([entry["signed_deviation"] for entry in readings])
    gauss_move = worst_move([entry["gauss_deviation"] for entry in readings])
    worst_gauss_removed = max(abs(entry["gauss_removed"]) for entry in readings)
    print("=" * 78)
    print(
        f"largest relative move between neighbouring spans: flat {flat_move:.3f}, "
        f"signed {signed_move:.3f}, gaussian {gauss_move:.3f}"
    )
    print(
        "the decaying member saturates"
        if gauss_move < 0.05
        else "the decaying member does not saturate over the declared spans"
    )
    print(f"gaussian closed-law residual, worst {worst_gauss_removed:.3e}")
    print(
        "margin k.a_G: change "
        + ", ".join(f"{entry['span']:.0f}:{entry['margin_change']:+.4f}" for entry in readings)
        + " | closed "
        + ", ".join(f"{entry['span']:.0f}:{entry['margin_closed']:+.4f}" for entry in readings)
    )
    print(
        f"margin law residual, worst "
        f"{max(entry['margin_residual'] for entry in readings):.3e}; "
        f"weighted critical-norm bound, worst ratio "
        f"{max(entry['margin_bound_ratio'] for entry in readings):.4f}"
    )
    print(json.dumps({"family": arguments.family, "readings": readings}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
