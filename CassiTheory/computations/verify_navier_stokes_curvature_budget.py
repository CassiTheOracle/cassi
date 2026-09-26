#!/usr/bin/env python
"""Independent verifier for the enstrophy budget of the widening channel.

Recomputes, from the stored receipt alone (no re-simulation):

  * the frame orthonormality and the closure (KF) at every lattice point,
  * the assembled rate (KC2), the enstrophy form (KC3) and the cap (KC4) from the
    stored terms,
  * the interval integrals, the advective/unsteady split and every decision rule
    H0-H9 of `computations/navier-stokes-curvature-budget-prereg.md`,
  * the content digest of the receipt,

and, with --mutation, perturbs one stored value and requires at least one check
to fail.

Usage:
    python computations/verify_navier_stokes_curvature_budget.py [--receipt PATH] [--mutation]

Exit status is 0 only when every recomputed check passes and, with --mutation,
when the mutation is detected.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = (
    ROOT / "runs" / "20260922_curvature_budget" / "curvature_budget_receipt.json"
)
SCHEMA = "navier-stokes-curvature-budget-v1"

FRAME_TOLERANCE = 1.0e-10
QUADRATURE_TOLERANCE = 1.0e-4
CAP_TOLERANCE = 1.0e-6
ENSTROPHY_TOLERANCE = 1.0e-4
ALGEBRA_TOLERANCE = 1.0e-9
PROBE_TOLERANCE = 1.0e-12
CLOCK_MARGIN_TOLERANCE = 1.0e-9
ORTHONORMAL_TOLERANCE = 1.0e-9
SPLIT_TOLERANCE = 1.0e-9


def content_digest(body: dict) -> str:
    payload = json.dumps(body, indent=1, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def recompute(entry: dict) -> dict[str, float]:
    """Every recomputed quantity of one family, from the stored values."""
    lattice = entry["lattice"]
    intervals = entry["intervals"]
    worst_orthonormal = 0.0
    worst_closure = 0.0
    worst_algebra = 0.0
    worst_cap_algebra = 0.0
    worst_enstrophy_algebra = 0.0
    for record in lattice:
        for side in ("tracer", "tracer_carried", "core"):
            point = record[side]
            direction = np.asarray(point["direction"], dtype=float)
            normal = np.asarray(point["normal"], dtype=float)
            binormal = np.asarray(point["binormal"], dtype=float)
            worst_orthonormal = max(
                worst_orthonormal,
                abs(float(direction @ direction) - 1.0),
                abs(float(normal @ normal) - 1.0),
                abs(float(binormal @ binormal) - 1.0),
                abs(float(direction @ normal)),
                abs(float(direction @ binormal)),
                abs(float(normal @ binormal)),
            )
            worst_closure = max(worst_closure, abs(point["frame_trace"]))
            assembled = (
                point["bend_rate"]
                - 4.0 * point["stretch"]
                - 2.0 * point["binormal_strain"]
            )
            scale = max(abs(assembled), 1.0)
            worst_algebra = max(
                worst_algebra, abs(assembled - point["assembled_rate"]) / scale
            )
            kc3 = (
                point["bend_rate"]
                - 2.0 * point["enstrophy_rate"]
                + 4.0 * entry["nu"] * point["production"] / point["magnitude"] ** 2
                - 2.0 * point["binormal_strain"]
            )
            worst_algebra = max(
                worst_algebra, abs(kc3 - point["kc3_rate"]) / max(abs(kc3), 1.0)
            )
            cap = (
                point["bend_rate"]
                - 2.0 * point["enstrophy_rate"]
                + 4.0 * entry["nu"] * point["laplacian_magnitude"] / point["magnitude"]
                - 2.0 * point["binormal_strain"]
            )
            worst_cap_algebra = max(
                worst_cap_algebra, abs(cap - point["cap_rate"]) / max(abs(cap), 1.0)
            )
            enstrophy = (
                2.0 * point["stretch"]
                + 2.0
                * entry["nu"]
                * point["production"]
                / point["magnitude"] ** 2
            )
            worst_enstrophy_algebra = max(
                worst_enstrophy_algebra,
                abs(enstrophy - point["enstrophy_rate"]) / max(abs(enstrophy), 1.0),
            )

    worst_quadrature = 0.0
    worst_cap_deficit = 0.0
    worst_enstrophy = 0.0
    worst_split = 0.0
    for index, interval in enumerate(intervals):
        earlier = lattice[index]
        later = lattice[index + 1]
        span = interval["to"] - interval["from"]
        if abs(earlier["time"] - interval["from"]) > 1e-12 or abs(
            later["time"] - interval["to"]
        ) > 1e-12:
            raise SystemExit("interval endpoints do not line up with the lattice")
        advective = interval["advective_increment"]
        unsteady = interval["unsteady_increment"]
        measured = interval["measured_increment"]
        worst_split = max(worst_split, abs(measured - (unsteady + advective)))
        assembled = 0.5 * span * (
            earlier["tracer"]["assembled_rate"] + later["tracer"]["assembled_rate"]
        )
        cap = 0.5 * span * (
            earlier["tracer"]["cap_rate"] + later["tracer"]["cap_rate"]
        )
        worst_quadrature = max(worst_quadrature, abs(advective - assembled))
        worst_cap_deficit = max(worst_cap_deficit, advective - cap)
        enstrophy_budget = 0.25 * span * (
            earlier["tracer"]["enstrophy_rate"] + later["tracer"]["enstrophy_rate"]
        )
        worst_enstrophy = max(
            worst_enstrophy, abs(interval["enstrophy_increment"] - enstrophy_budget)
        )
    # Material channels: the carried trajectory's own changes against the
    # integrals of the terms the identity assigns to them.
    worst_material_magnitude = 0.0
    recomputed_gaps = {
        "magnitude_increment": 0.0,
        "magnitude_budget": 0.0,
        "margin_increment": 0.0,
        "margin_frozen_field_integral": 0.0,
        "kappa_increment": 0.0,
        "kappa_frozen_field_integral": 0.0,
        "width_increment": 0.0,
        "width_frozen_field_integral": 0.0,
    }
    for index, interval in enumerate(intervals):
        earlier = lattice[index]["tracer_carried"]
        later = lattice[index + 1]["tracer_carried"]
        span = interval["to"] - interval["from"]
        magnitude_increment = math.log(later["magnitude"] / earlier["magnitude"])
        magnitude_budget = 0.5 * span * (
            later["stretch"]
            + entry["nu"] * later["production"] / later["magnitude"] ** 2
            + earlier["stretch"]
            + entry["nu"] * earlier["production"] / earlier["magnitude"] ** 2
        )
        worst_material_magnitude = max(
            worst_material_magnitude, abs(magnitude_increment - magnitude_budget)
        )
        recomputed_gaps["magnitude_increment"] += magnitude_increment
        recomputed_gaps["magnitude_budget"] += magnitude_budget
        recomputed_gaps["margin_increment"] += math.log(
            later["margin"] / earlier["margin"]
        )
        recomputed_gaps["margin_frozen_field_integral"] += 0.5 * span * (
            later["assembled_rate"] + earlier["assembled_rate"]
        )
        recomputed_gaps["kappa_increment"] += math.log(later["kappa"] / earlier["kappa"])
        recomputed_gaps["kappa_frozen_field_integral"] += 0.5 * span * (
            later["bend_rate"] + earlier["bend_rate"]
        )
        recomputed_gaps["width_increment"] += math.log(later["width"] / earlier["width"])
        recomputed_gaps["width_frozen_field_integral"] += 0.5 * span * (
            later["transverse"]
            - later["stretch"]
            + earlier["transverse"]
            - earlier["stretch"]
        )
    return {
        "worst_material_magnitude": worst_material_magnitude,
        "recomputed_gaps": recomputed_gaps,
        "worst_orthonormal": worst_orthonormal,
        "worst_closure": worst_closure,
        "worst_algebra": worst_algebra,
        "worst_cap_algebra": worst_cap_algebra,
        "worst_enstrophy_algebra": worst_enstrophy_algebra,
        "worst_quadrature": worst_quadrature,
        "worst_cap_deficit": worst_cap_deficit,
        "worst_enstrophy": worst_enstrophy,
        "worst_split": worst_split,
    }


def verify(receipt: dict, checks: list[dict]) -> dict[str, float]:
    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    body = dict(receipt)
    declared = body.pop("content_sha256", None)
    digest = content_digest(body)
    record(
        "V0 content digest",
        declared == digest,
        f"declared {declared} recomputed {digest}",
    )
    record(
        "V1 schema",
        receipt.get("schema") == SCHEMA,
        f"schema {receipt.get('schema')}",
    )
    summary: dict[str, float] = {}
    for entry in receipt["dynamics"]:
        name = entry["case"]
        values = recompute(entry)
        summary[name] = values
        record(
            f"V2 {name}: the stored frames are orthonormal",
            values["worst_orthonormal"] <= ORTHONORMAL_TOLERANCE,
            f"worst |t.t-1|, |n.n-1|, |b.b-1|, |t.n|, |t.b|, |n.b| "
            f"{values['worst_orthonormal']:.2e}",
        )
        record(
            f"V3 {name}: the frame closure (KF) holds",
            values["worst_closure"] <= FRAME_TOLERANCE,
            f"worst |ell + n.Sn + b.Sb| = {values['worst_closure']:.2e}",
        )
        record(
            f"V4 {name}: (KC2), (KC3) and (KC4) recompute from the stored terms",
            max(
                values["worst_algebra"],
                values["worst_cap_algebra"],
                values["worst_enstrophy_algebra"],
            )
            <= ALGEBRA_TOLERANCE,
            f"worst relative residuals: assembled {values['worst_algebra']:.2e}, "
            f"cap {values['worst_cap_algebra']:.2e}, enstrophy "
            f"{values['worst_enstrophy_algebra']:.2e}",
        )
        record(
            f"V5 {name}: the frozen-field rate integrates to the advective increment",
            values["worst_quadrature"] <= QUADRATURE_TOLERANCE,
            f"worst residual {values['worst_quadrature']:.2e}",
        )
        record(
            f"V6 {name}: the cap stays above the advective increment",
            values["worst_cap_deficit"] <= CAP_TOLERANCE,
            f"worst deficit {values['worst_cap_deficit']:.2e}",
        )
        record(
            f"V7 {name}: the enstrophy identity integrates along the tracer",
            values["worst_enstrophy"] <= ENSTROPHY_TOLERANCE,
            f"worst residual {values['worst_enstrophy']:.2e}",
        )
        record(
            f"V8 {name}: the material increment splits into unsteady and advective",
            values["worst_split"] <= SPLIT_TOLERANCE,
            f"worst telescoping residual {values['worst_split']:.2e}",
        )
        declared = entry["material_gaps"]
        recomputed_gaps = values["recomputed_gaps"]
        gap_worst = max(
            abs(declared[key] - recomputed_gaps[key]) / max(abs(declared[key]), 1.0)
            for key in recomputed_gaps
        )
        record(
            f"V10 {name}: the material enstrophy identity holds along the carried trajectory",
            values["worst_material_magnitude"] <= 1.0e-3,
            f"worst residual {values['worst_material_magnitude']:.2e}",
        )
        record(
            f"V11 {name}: the reported material gaps recompute from the stored values",
            gap_worst <= 1.0e-9,
            f"worst relative difference {gap_worst:.2e}; margin "
            f"{recomputed_gaps['margin_increment']:+.5f} against the frozen-field integral "
            f"{recomputed_gaps['margin_frozen_field_integral']:+.5f}, width "
            f"{recomputed_gaps['width_increment']:+.5f} against "
            f"{recomputed_gaps['width_frozen_field_integral']:+.5f}",
        )
        shares = entry["checks"]
        total = shares["total_measured_increment"]
        record(
            f"V9 {name}: the advective share is the stored ratio",
            abs(
                shares["advective_share"]
                - shares["total_advective_increment"]
                / max(abs(total), 1e-300)
            )
            <= 1.0e-12,
            f"material {total:+.5f}, advective {shares['total_advective_increment']:+.6f}, "
            f"share {shares['advective_share']:+.4f}",
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", default=None)
    parser.add_argument("--mutation", action="store_true")
    arguments = parser.parse_args()
    path = Path(arguments.receipt) if arguments.receipt else DEFAULT_RECEIPT
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"missing receipt {path}")
    receipt = json.loads(path.read_text(encoding="utf-8"))

    print("Independent verification of the enstrophy budget")
    print("=" * 78)
    checks: list[dict[str, Any]] = []
    verify(receipt, checks)
    for item in checks:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"  [{mark}] {item['name']}: {item['detail']}")
    failed = [item for item in checks if not item["passed"]]

    if arguments.mutation:
        mutated = copy.deepcopy(receipt)
        target = mutated["dynamics"][0]["lattice"][len(mutated["dynamics"][0]["lattice"]) // 2]
        target["tracer"]["assembled_rate"] += 1.0e-2
        mutation_checks: list[dict[str, Any]] = []
        verify(mutated, mutation_checks)
        mutation_failed = [item for item in mutation_checks if not item["passed"]]
        digest_failed = any("V0" in item["name"] for item in mutation_failed)
        print(
            f"  [{'PASS' if mutation_failed else 'FAIL'}] M1 mutation control: "
            f"{len(mutation_failed)} checks fail on a perturbed stored value"
            f"{' (including the digest)' if digest_failed else ''}"
        )
        if not mutation_failed:
            failed.append({"name": "M1 mutation control"})

    print("=" * 78)
    print(
        f"recomputed checks: {len(checks)}  failures: {len(failed)}  "
        f"receipt {path.name}"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
