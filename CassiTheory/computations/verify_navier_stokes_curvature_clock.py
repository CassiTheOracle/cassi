#!/usr/bin/env python3
"""Independent verifier for the curvature-clock receipt.

Recomputes the kinematic identity (KC1) from the closed forms of the three
control families, recomputes every derived checkpoint quantity from the stored
raw tensors, and re-derives the declared claims.  Nothing is imported from the
producer: the closed forms and the coherence algebra live here.

    python computations/verify_navier_stokes_curvature_clock.py
    python computations/verify_navier_stokes_curvature_clock.py --receipt <path>
    python computations/verify_navier_stokes_curvature_clock.py --mutation

Exit code is zero when every check passes (or, under --mutation, when at least
one check fails).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = (
    ROOT / "runs" / "20260921_curvature_clock" / "curvature_clock_receipt.json"
)

RELATIVE_TOLERANCE = 1.0e-9
DECLARED_TOLERANCE = 1.0e-8
HELIX_BAND = (0.5, 2.0)
COEFFICIENT_BAND = (0.3, 3.0)
QUADRATURE_ORDER = 8

RESULTS: list[dict[str, object]] = []


def check(name: str, passed: bool, detail: str) -> None:
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})


def relative(a: float, b: float, scale: float = 1.0) -> float:
    return abs(a - b) / max(abs(scale), 1e-300)


def content_digest(body: dict) -> str:
    payload = json.dumps(body, indent=1, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------
# closed forms of the declared control families (independent of the producer)
# --------------------------------------------------------------------------
def control_forms(control: dict):
    """Return (margin(t), rate(t), description) for one declared control."""
    parameters = control["parameters"]
    name = str(control["name"])
    if name == "parabolic_bend":
        beta = float(parameters["beta"])
        width = float(parameters["normal_width"])
        return (
            lambda time: 2.0 * beta * time * width,
            lambda time: 1.0 / time,
            f"kappa = 2 beta t with beta {beta:g}, a_n = {width:g} constant",
        )
    if name == "ellipse_tip":
        alpha = float(parameters["alpha"])
        kappa_zero = 1.0 / float(parameters["ring_radius"])
        width_zero = float(parameters["normal_width"])
        return (
            lambda time: kappa_zero * width_zero * math.exp(4.0 * alpha * time),
            lambda time: 4.0 * alpha,
            f"kappa ~ e^(3 alpha t), a_n ~ e^(alpha t), margin ~ e^(4 alpha t), alpha {alpha:g}",
        )
    if name == "axisymmetric_ring":
        kappa_zero = 1.0 / float(parameters["ring_radius"])
        width_zero = float(parameters["normal_width"])
        return (
            lambda time: kappa_zero * width_zero,
            lambda time: 0.0,
            f"kappa a_n = kappa_0 a_n = {kappa_zero * width_zero:g} conserved exactly",
        )
    raise SystemExit(f"unknown control {name}")


def control_check(control: dict, mutation_note: str) -> None:
    name = str(control["name"])
    rows = control["rows"]
    margin, rate, description = control_forms(control)
    worst_margin = 0.0
    worst_rate = 0.0
    worst_closure = 0.0
    stale_ratios = 0
    for row in rows:
        time = float(row["time"])
        expected = margin(time)
        worst_margin = max(worst_margin, relative(float(row["margin"]), expected, expected))
        expected_rate = rate(time)
        worst_rate = max(worst_rate, abs(float(row["rate"]) - expected_rate))
        closure = (
            float(row["inhomogeneous"]) / float(row["kappa"])
            + 2.0 * float(row["transverse"])
            - 2.0 * float(row["stretch"])
        )
        worst_closure = max(
            worst_closure,
            abs(closure - float(row["rate"])) / max(float(row["term_scale"]), 1e-12),
        )
        if relative(float(row["closed_form_margin"]), expected, expected) > RELATIVE_TOLERANCE:
            stale_ratios += 1
    check(
        f"V3 {name}: stored margin reproduces the closed form",
        worst_margin <= RELATIVE_TOLERANCE,
        f"worst relative margin deviation {worst_margin:.2e}{mutation_note}",
    )
    check(
        f"V4 {name}: stored rate reproduces the closed form",
        worst_rate <= 1.0e-6,
        f"worst absolute rate deviation {worst_rate:.2e}",
    )
    check(
        f"V5 {name}: stored identity terms close on the stored rate",
        worst_closure <= RELATIVE_TOLERANCE,
        f"worst scaled closure residual {worst_closure:.2e}",
    )
    check(
        f"V6 {name}: stored closed-form margins agree with the recomputed ones",
        stale_ratios == 0,
        f"{stale_ratios} of {len(rows)} samples outside the tolerance",
    )

    worst_interval = 0.0
    worst_pointwise = 0.0
    nodes, weights = np.polynomial.legendre.leggauss(QUADRATURE_ORDER)
    for interval in control["intervals"]:
        left = float(interval["from"])
        right = float(interval["to"])
        measured = float(interval["measured_increment"])
        if name == "parabolic_bend":
            expected = math.log(margin(right) / margin(left))
        else:
            expected = rate(left) * (right - left)
        worst_interval = max(worst_interval, abs(measured - expected))
        centred = 0.5 * (left + right) + 0.5 * (right - left) * nodes
        quadrature = 0.5 * (right - left) * float(
            np.sum(weights * np.array([rate(float(node)) for node in centred]))
        )
        worst_pointwise = max(
            worst_pointwise,
            abs(float(interval["predicted_increment"]) - quadrature),
        )
    check(
        f"V7 {name}: measured margin increments match the analytic integral",
        worst_interval <= DECLARED_TOLERANCE,
        f"worst increment residual {worst_interval:.2e}{mutation_note}",
    )
    check(
        f"V8 {name}: the stored Gauss-Legendre increment matches an independent quadrature",
        worst_pointwise <= 1.0e-11,
        f"worst quadrature deviation {worst_pointwise:.2e}",
    )
    if name == "parabolic_bend":
        beta = float(control["parameters"]["beta"])
        width = float(control["parameters"]["normal_width"])
        pole_time = float(control["parameters"]["pole_time"])
        check(
            "V9 parabolic bend: reported pole time follows 1/(2 beta a_n)",
            relative(pole_time, 1.0 / (2.0 * beta * width), pole_time) <= RELATIVE_TOLERANCE,
            f"stored pole time {pole_time:.9f}",
        )
        pole = control["pole"]
        check(
            "V10 parabolic bend: the margin is exactly one at the reported pole time",
            abs(float(pole["margin"]) - 1.0) <= 1.0e-9,
            f"margin {float(pole['margin']):.12f} at t = {pole_time:.6f}",
        )


# --------------------------------------------------------------------------
# recomputation of the derived checkpoint quantities from the raw tensors
# --------------------------------------------------------------------------
def recompute(raw: dict) -> dict:
    omega = np.asarray(raw["omega"], dtype=float)
    gradient_omega = np.asarray(raw["gradient_omega"], dtype=float)
    magnitude = float(raw["magnitude"])
    gradient_magnitude = np.asarray(raw["gradient_magnitude"], dtype=float)
    hessian_magnitude = np.asarray(raw["hessian_magnitude"], dtype=float)
    gradient_u = np.asarray(raw["velocity_gradient"], dtype=float)
    second_u = np.asarray(raw["second_velocity"], dtype=float)

    direction = omega / magnitude
    gradient_direction = (
        gradient_omega / magnitude
        - np.outer(omega, gradient_magnitude) / (magnitude * magnitude)
    )
    curvature_vector = np.einsum("j,ij->i", direction, gradient_direction)
    kappa = float(np.linalg.norm(curvature_vector))
    normal = curvature_vector / kappa
    curvature_second = float(normal @ hessian_magnitude @ normal)
    width = math.sqrt(abs(magnitude / curvature_second))
    strain = 0.5 * (gradient_u + gradient_u.T)
    stretch = float(direction @ gradient_u @ direction)
    transverse = float(normal @ strain @ normal)
    inhomogeneous = float(np.einsum("i,l,ijl,j->", normal, direction, second_u, direction))
    predicted = inhomogeneous / kappa + 2.0 * transverse - 2.0 * stretch

    coefficients = {}
    for key, sample in raw["direction_samples"].items():
        neighbour = np.asarray(sample["direction"], dtype=float)
        displacement = float(sample["displacement"])
        variation = float(np.linalg.norm(neighbour - direction))
        coefficients[key] = {
            "variation": variation,
            "coefficient": variation / (displacement * kappa),
            "displacement": displacement,
        }
    return {
        "direction": direction,
        "normal": normal,
        "kappa": kappa,
        "width": width,
        "margin": kappa * width,
        "stretch": stretch,
        "transverse": transverse,
        "inhomogeneous": inhomogeneous,
        "predicted_rate": predicted,
        "coefficients": coefficients,
    }


def dynamics_check(entry: dict, mutation_note: str) -> None:
    name = str(entry["case"])
    seeded = float(entry["helix_curvature"])
    margins = []
    for checkpoint in entry["checkpoints"]:
        raw = checkpoint["raw"]
        stored = checkpoint["derived"]
        local = recompute(raw)
        where = f"{name} step {checkpoint['step']}"
        worst = 0.0
        for key in ("kappa", "width", "margin", "stretch", "transverse", "inhomogeneous"):
            stored_value = abs(float(stored[key]))
            worst = max(
                worst,
                relative(float(stored[key]), float(local[key]), max(stored_value, 1e-12)),
            )
        check(
            f"V11 {where}: derived tensors recompute from the raw tensors",
            worst <= RELATIVE_TOLERANCE,
            f"worst relative deviation {worst:.2e}{mutation_note}",
        )
        recovery = (
            float(stored["inhomogeneous"]) / float(stored["kappa"])
            + 2.0 * float(stored["transverse"])
            - 2.0 * float(stored["stretch"])
        )
        scale = max(abs(float(stored["kappa"])), 1e-12)
        check(
            f"V12 {where}: rate identity closes on the recomputed terms",
            abs(recovery - float(stored["predicted_rate"]))
            <= RELATIVE_TOLERANCE * scale,
            f"closure residual {abs(recovery - float(stored['predicted_rate'])):.2e}",
        )
        direction_delta = float(
            np.linalg.norm(np.asarray(stored["direction"], dtype=float) - local["direction"])
        )
        normal_delta = float(
            np.linalg.norm(np.asarray(stored["normal"], dtype=float) - local["normal"])
        )
        check(
            f"V13 {where}: core direction and normal recompute",
            direction_delta <= 1.0e-9 and normal_delta <= 1.0e-9,
            f"direction deviation {direction_delta:.2e}, normal deviation {normal_delta:.2e}",
        )
        worst_coefficient = 0.0
        for key, value in stored["coherence_coefficient"].items():
            local_value = local["coefficients"][key]
            worst_coefficient = max(
                worst_coefficient,
                relative(
                    float(value["variation"]),
                    local_value["variation"],
                    max(abs(float(value["variation"])), 1e-12),
                ),
                relative(
                    float(value["coefficient"]),
                    local_value["coefficient"],
                    max(abs(float(value["coefficient"])), 1e-12),
                ),
            )
        check(
            f"V14 {where}: neighbour coherence coefficients recompute",
            worst_coefficient <= RELATIVE_TOLERANCE,
            f"worst relative deviation {worst_coefficient:.2e}",
        )
        spacing = float(raw["spacing"])
        worst_grid = max(
            abs(float(sample["displacement"]) - float(sample["cells"]) * spacing)
            for sample in raw["direction_samples"].values()
        )
        check(
            f"V15 {where}: neighbour displacements follow the grid spacing",
            worst_grid <= 1.0e-12,
            f"worst displacement deviation {worst_grid:.2e}",
        )
        size = int(raw["grid_size"])
        check(
            f"V16 {where}: the grid spacing follows the declared box size",
            relative(float(raw["spacing"]), 2.0 * math.pi / size, float(raw["spacing"]))
            <= RELATIVE_TOLERANCE,
            f"spacing {float(raw['spacing']):.9f} on a {size}^3 grid",
        )
        margins.append(float(stored["margin"]))

    growth = [margins[index + 1] - margins[index] for index in range(len(margins) - 1)]
    check(
        f"V17 {name}: the coherence margin grows monotonically over the checkpoints",
        all(value > 0.0 for value in growth),
        "increments " + ", ".join(f"{value:.4f}" for value in growth),
    )
    check(
        f"V18 {name}: the coherence margin stays inside the pole",
        max(margins) < 1.0,
        f"largest margin {max(margins):.6f}",
    )
    anchor = float(entry["checkpoints"][0]["derived"]["kappa"]) / seeded
    check(
        f"V19 {name}: the initial core curvature anchors to the seeded helix",
        HELIX_BAND[0] <= anchor <= HELIX_BAND[1],
        f"measured ratio {anchor:.4f} at t = {float(entry['checkpoints'][0]['time']):g}, "
        f"declared band {HELIX_BAND}",
    )
    first_coefficients = [
        float(value["coefficient"])
        for value in entry["checkpoints"][0]["derived"]["coherence_coefficient"].values()
    ]
    check(
        f"V20 {name}: the near-field coherence coefficient is order one",
        all(COEFFICIENT_BAND[0] <= value <= COEFFICIENT_BAND[1] for value in first_coefficients),
        "coefficients " + ", ".join(f"{value:.4f}" for value in first_coefficients),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--mutation", action="store_true")
    arguments = parser.parse_args()

    path = Path(arguments.receipt)
    document = json.loads(path.read_text(encoding="utf-8"))
    mutation_note = ""

    body = {key: value for key, value in document.items() if key != "content_sha256"}
    digest = content_digest(body)
    if arguments.mutation:
        mutation_note = " [mutated]"
        document["dynamics"][0]["checkpoints"][1]["raw"]["magnitude"] *= 1.01
        document["dynamics"][0]["checkpoints"][1]["raw"]["velocity_gradient"][0][0] += 1.0e-3
        document["controls"][0]["rows"][1]["margin"] *= 1.01
        check(
            "V0 mutation control: the injected perturbations are visible",
            True,
            "checkpoint magnitude, one velocity-gradient component and one control margin perturbed",
        )
    else:
        check(
            "V1 content digest reproduces",
            digest == document["content_sha256"],
            f"recomputed {digest[:16]} against stored {document['content_sha256'][:16]}",
        )

    for control in document["controls"]:
        control_check(control, mutation_note)
    for entry in document["dynamics"]:
        dynamics_check(entry, mutation_note)

    reported = {item["name"]: item["passed"] for item in document["checks"]}
    check(
        "V21 every check recorded in the receipt passed",
        all(reported.values()),
        f"{sum(reported.values())} of {len(reported)} stored checks passed",
    )
    check(
        "V22 the receipt status matches its checks",
        (document["status"] == "PASS") == all(reported.values()),
        f"status {document['status']}",
    )

    failures = [item for item in RESULTS if not item["passed"]]
    for item in RESULTS:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"  [{mark}] {item['name']}: {item['detail']}")
    print("=" * 78)
    print(f"checks {len(RESULTS)}  failures {len(failures)}")
    if arguments.mutation:
        print("mutation control " + ("FIRED" if failures else "SILENT"))
        return 0 if failures else 1
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
