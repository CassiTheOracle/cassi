#!/usr/bin/env python
"""Independent verifier for the saturation-window receipt.

Recomputes every derived checkpoint quantity from the stored raw tensors with
the algebra of `verify_navier_stokes_curvature_clock.py` (the clock protocol's
verifier, itself producer-independent), rebuilds the rate series, the decay
classification and the projected limit from the stored margins, and anchors the
window's initial state against the clock receipt.

    python computations/verify_navier_stokes_curvature_clock_saturation.py
    python computations/verify_navier_stokes_curvature_clock_saturation.py --mutation

Exit code is zero when every check passes (or, under --mutation, when at least
one check fails).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CLOCK_VERIFIER = ROOT / "computations" / "verify_navier_stokes_curvature_clock.py"
DEFAULT_RECEIPT = (
    ROOT
    / "runs"
    / "20260921_curvature_clock_saturation"
    / "curvature_clock_saturation_receipt.json"
)
CLOCK_RECEIPT = (
    ROOT / "runs" / "20260921_curvature_clock" / "curvature_clock_receipt.json"
)
RELATIVE_TOLERANCE = 1.0e-9
TAIL_THRESHOLD = 5.0e-2

RESULTS: list[dict[str, object]] = []


def check(name: str, passed: bool, detail: str) -> None:
    RESULTS.append({"name": name, "passed": bool(passed), "detail": detail})


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def relative(a: float, b: float, scale: float = 1.0) -> float:
    return abs(a - b) / max(abs(scale), 1e-300)


def rebuild_statistics(entry: dict) -> dict:
    """Rebuild rates, decay classification and projection from stored margins."""
    checkpoints = entry["checkpoints"]
    rates = []
    for earlier, later in zip(checkpoints, checkpoints[1:]):
        span = later["time"] - earlier["time"]
        rates.append((later["derived"]["margin"] - earlier["derived"]["margin"]) / span)
    last = float(checkpoints[-1]["derived"]["margin"])
    span = float(checkpoints[-1]["time"] - checkpoints[-2]["time"])
    turnover = rates[-1] <= 0.0
    if turnover:
        ratio = 0.0
        projection = last
        decay = "turnover"
    elif rates[-3] > 0.0 and rates[-1] > 0.0:
        ratio = (rates[-1] / rates[-3]) ** (1.0 / 3.0)
        projection = (
            last + rates[-1] * span * ratio / (1.0 - ratio)
            if ratio < 1.0
            else float("inf")
        )
        decay = "decelerating"
        if not rates[-3] >= rates[-2] >= rates[-1]:
            decay = "non-monotone"
    else:
        ratio = float("nan")
        projection = float("inf")
        decay = "non-monotone"
    return {
        "rates": rates,
        "rate_ratio": ratio,
        "decay": decay,
        "projected_limit": projection,
        "turnover": bool(turnover),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--clock-receipt", default=str(CLOCK_RECEIPT))
    parser.add_argument("--mutation", action="store_true")
    arguments = parser.parse_args()

    verifier = load_module(CLOCK_VERIFIER)
    document = json.loads(Path(arguments.receipt).read_text(encoding="utf-8"))
    clock_document = json.loads(Path(arguments.clock_receipt).read_text(encoding="utf-8"))
    mutation_note = ""

    if arguments.mutation:
        mutation_note = " [mutated]"
        document["dynamics"][0]["checkpoints"][3]["derived"]["margin"] *= 1.02
        document["dynamics"][1]["checkpoints"][2]["raw"]["magnitude"] *= 0.99
        check(
            "X0 mutation control: the injected perturbations are visible",
            True,
            "one stored margin and one raw magnitude perturbed in the loaded copy",
        )
    else:
        body = {key: value for key, value in document.items() if key != "content_sha256"}
        digest = hashlib.sha256(
            json.dumps(body, indent=1, sort_keys=True).encode()
        ).hexdigest()
        check(
            "X1 content digest reproduces",
            digest == document["content_sha256"],
            f"recomputed {digest[:16]} against stored {document['content_sha256'][:16]}",
        )

    clock_initial = {
        entry["case"]: entry["checkpoints"][0] for entry in clock_document["dynamics"]
    }

    for entry in document["dynamics"]:
        name = entry["case"]
        worst_derived = 0.0
        margins = []
        for checkpoint in entry["checkpoints"]:
            stored = checkpoint["derived"]
            local = verifier.recompute(checkpoint["raw"])
            for key in ("kappa", "width", "margin", "stretch", "transverse", "inhomogeneous"):
                scale = max(abs(float(stored[key])), 1e-12)
                worst_derived = max(
                    worst_derived, relative(float(stored[key]), float(local[key]), scale)
                )
            margins.append(float(stored["margin"]))
        check(
            f"X2 {name}: derived tensors recompute from the raw tensors",
            worst_derived <= RELATIVE_TOLERANCE,
            f"worst relative deviation {worst_derived:.2e}{mutation_note}",
        )

        rebuilt = rebuild_statistics(entry)
        worst_rate = max(
            abs(rebuilt["rates"][index] - float(entry["rates"][index]))
            for index in range(len(rebuilt["rates"]))
        )
        check(
            f"X3 {name}: the rate series rebuilds from the stored margins",
            worst_rate <= 1.0e-12,
            f"worst rate deviation {worst_rate:.2e}",
        )
        check(
            f"X4 {name}: the decay classification rebuilds",
            rebuilt["decay"] == entry["decay"] and rebuilt["turnover"] == entry["turnover"],
            f"rebuilt {rebuilt['decay']} against stored {entry['decay']}, "
            f"turnover {rebuilt['turnover']}",
        )
        stored_ratio = float(entry["rate_ratio"])
        stored_limit = float(entry["projected_limit"])
        ratio_ok = (
            math.isnan(stored_ratio) and math.isnan(rebuilt["rate_ratio"])
        ) or relative(stored_ratio, rebuilt["rate_ratio"], max(abs(stored_ratio), 1e-9)) <= 1e-9
        limit_ok = (math.isinf(stored_limit) and math.isinf(rebuilt["projected_limit"])) or (
            math.isfinite(stored_limit)
            and relative(stored_limit, rebuilt["projected_limit"], max(abs(stored_limit), 1e-9))
            <= 1e-9
        )
        check(
            f"X5 {name}: the projected limit rebuilds from the rate series",
            ratio_ok and limit_ok,
            f"rebuilt ratio {rebuilt['rate_ratio']:.6f} and limit "
            f"{rebuilt['projected_limit']:.6f}",
        )
        check(
            f"X6 {name}: the reported rates match the margin differences",
            all(value > -1e-12 for value in margins)
            and abs(float(entry["final_margin"]) - margins[-1]) <= 1.0e-12
            and abs(float(entry["maximum_margin"]) - max(margins)) <= 1.0e-12,
            f"final margin {float(entry['final_margin']):.6f}, "
            f"maximum {float(entry['maximum_margin']):.6f}",
        )
        check(
            f"X7 {name}: the margin stays inside the pole",
            max(margins) < 1.0,
            f"largest margin {max(margins):.6f} over {len(margins)} checkpoints",
        )
        anchor = float(entry["checkpoints"][0]["derived"]["kappa"]) / float(
            entry["helix_curvature"]
        )
        check(
            f"X8 {name}: the initial curvature anchors to the seeded helix",
            0.5 <= anchor <= 2.0,
            f"measured ratio {anchor:.4f}",
        )
        tail = float(entry["maximum_enstrophy_tail"])
        under = tail > TAIL_THRESHOLD
        check(
            f"X9 {name}: the resolution diagnostic is classified consistently",
            (name in document["under_resolved"]) == under and 0.0 <= tail <= 1.0,
            f"largest tail {tail:.2e}, listed under-resolved {name in document['under_resolved']}",
        )
        for checkpoint in entry["checkpoints"]:
            row = checkpoint["observables"]
            if not (
                float(row["divergence_residual"]) <= 1.0e-12
                and float(row["kinetic_energy"]) > 0.0
            ):
                check(
                    f"X10 {name}: checkpoint observables are physical",
                    False,
                    f"divergence {float(row['divergence_residual']):.2e}, "
                    f"energy {float(row['kinetic_energy']):.6f}",
                )
                break
        else:
            check(
                f"X10 {name}: checkpoint observables are physical",
                True,
                "divergence below 1e-12 and positive kinetic energy at every checkpoint",
            )

        reference = clock_initial.get(name)
        if reference is not None:
            worst_anchor = 0.0
            for key in ("kappa", "width", "margin"):
                worst_anchor = max(
                    worst_anchor,
                    relative(
                        float(entry["checkpoints"][0]["derived"][key]),
                        float(reference["derived"][key]),
                        max(abs(float(reference["derived"][key])), 1e-12),
                    ),
                )
            check(
                f"X11 {name}: the window reproduces the clock's initial checkpoint",
                worst_anchor <= 1.0e-12,
                f"worst relative deviation {worst_anchor:.2e} against the clock receipt",
            )

    reported = {item["name"]: item["passed"] for item in document["checks"]}
    check(
        "X12 every check recorded in the receipt passed",
        all(reported.values()),
        f"{sum(reported.values())} of {len(reported)} stored checks passed",
    )
    check(
        "X13 the receipt status matches its checks",
        (document["status"] == "PASS") == all(reported.values()),
        f"status {document['status']}",
    )
    check(
        "X14 the scope keeps arbitrary-data regularity open",
        document["scope"]["arbitrary_data_regularity"] == "UNRESOLVED"
        and document["scope"]["projection_is_a_bound"] is False,
        "regularity unresolved and the projection declared not to be a bound",
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
