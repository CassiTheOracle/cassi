"""Verify the local Yang--Mills character-cutoff density theorem.

This deterministic verifier checks the periodic-cubic local bound, the joint
auxiliary-cutoff schedule, and the gauge-invariant global-norm obstruction.
It does not construct a thermodynamic or continuum Yang--Mills state.

Run from the CassiTheory root:

    python computations/verify_yang_mills_local_cutoff_density.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "yang-mills-local-cutoff-density-prereg.md"
OUTPUT = ROOT / "runs" / "yang_mills_local_cutoff_density" / "verification.json"

VOLUMES = (3, 4, 6, 8, 12, 16, 24, 32)
COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0, 4.0, 16.0)
SUPPORT_SIZES = (1, 4, 6, 12)
CUTOFFS = (1, 2, 4, 8, 16, 32, 64, 128)
JOINT_SCALES = (2, 4, 8, 16, 32, 64, 128)
PRODUCT_Q = (0.25, 0.5, 0.75)
PRODUCT_CUTOFFS = (0, 1, 2, 4, 8)
PRODUCT_VOLUMES = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 4096)
EPSILON = 0.1
SERIES_TERMINAL = 4096
TOLERANCE = 1.0e-12


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    measured: Any,
    requirement: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "measured": measured,
            "requirement": requirement,
        }
    )


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=TOLERANCE, abs_tol=TOLERANCE)


def kappa(cutoff: int) -> float:
    return (cutoff + 1.0) * (cutoff + 3.0) / 4.0


def observable_envelope(tail_bound: float) -> float | None:
    if not 0.0 <= tail_bound < 1.0:
        return None
    return 2.0 * math.sqrt(tail_bound) + tail_bound


def one_loop_tail(q: float, cutoff: int) -> float:
    return q ** (2 * (cutoff + 1))


def retained_norm_stable(q: float, cutoff: int, loops: int) -> float:
    tail = one_loop_tail(q, cutoff)
    return math.exp(loops * math.log1p(-tail))


def discarded_norm_stable(q: float, cutoff: int, loops: int) -> float:
    tail = one_loop_tail(q, cutoff)
    return -math.expm1(loops * math.log1p(-tail))


def retained_norm_iterative(q: float, cutoff: int, loops: int) -> float:
    factor = 1.0 - one_loop_tail(q, cutoff)
    retained = 1.0
    for _ in range(loops):
        retained *= factor
    return retained


def electric_energy_per_loop(q: float) -> float:
    q2 = q * q
    return q2 * (3.0 - q2) / ((1.0 - q2) ** 2)


def direct_tail_sum(q: float, cutoff: int) -> float:
    q2 = q * q
    weight = (1.0 - q2) * q2 ** (cutoff + 1)
    total = 0.0
    for _ in range(cutoff + 1, SERIES_TERMINAL + 1):
        total += weight
        weight *= q2
    return total


def direct_energy_sum(q: float) -> float:
    q2 = q * q
    weight = 1.0 - q2
    total = 0.0
    for label in range(SERIES_TERMINAL + 1):
        total += label * (label + 2.0) * weight
        weight *= q2
    return total


def minimum_cutoff_formula(loops: int, q: float, epsilon: float) -> int:
    maximum_tail = -math.expm1(math.log1p(-epsilon) / loops)
    threshold = math.log(maximum_tail) / (2.0 * math.log(q)) - 1.0
    return max(0, math.ceil(threshold))


def minimum_cutoff_search(loops: int, q: float, epsilon: float) -> int:
    cutoff = 0
    target = 1.0 - epsilon
    while retained_norm_stable(q, cutoff, loops) < target:
        cutoff += 1
    return cutoff


def run(output: Path, replace: bool) -> dict[str, Any]:
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    checks: list[dict[str, Any]] = []
    local_rows: list[dict[str, Any]] = []
    applicable = 0
    kappa_error = 0.0

    for side in VOLUMES:
        edges = 3 * side**3
        plaquettes = 3 * side**3
        for coupling in COUPLINGS:
            trial_energy = 2.0 * coupling * plaquettes
            energy_per_edge = trial_energy / edges
            for support in SUPPORT_SIZES:
                for cutoff in CUTOFFS:
                    threshold = kappa(cutoff)
                    excluded_spin = (cutoff + 1.0) / 2.0
                    direct_threshold = excluded_spin * (excluded_spin + 1.0)
                    kappa_error = max(kappa_error, abs(threshold - direct_threshold))
                    tail_bound = support * energy_per_edge / threshold
                    envelope = observable_envelope(tail_bound)
                    if envelope is not None:
                        applicable += 1
                    local_rows.append(
                        {
                            "side_L": side,
                            "edge_count": edges,
                            "plaquette_count": plaquettes,
                            "coupling_x": coupling,
                            "support_links": support,
                            "cutoff_C": cutoff,
                            "kappa_C": threshold,
                            "trial_energy_bound": trial_energy,
                            "energy_bound_per_edge": energy_per_edge,
                            "local_tail_bound": tail_bound,
                            "applicable": envelope is not None,
                            "unit_observable_error_bound": envelope,
                        }
                    )

    expected_local_rows = (
        len(VOLUMES) * len(COUPLINGS) * len(SUPPORT_SIZES) * len(CUTOFFS)
    )
    add_check(
        checks,
        "local_schedule_coverage",
        len(local_rows) == expected_local_rows == 1536,
        {"rows": len(local_rows), "expected": expected_local_rows},
        "all 1536 frozen local rows are present",
    )
    add_check(
        checks,
        "periodic_cubic_combinatorics",
        all(
            row["edge_count"] == row["plaquette_count"] == 3 * row["side_L"] ** 3
            for row in local_rows
        ),
        {"volumes": list(VOLUMES)},
        "|E_L| = N_p,L = 3 L^3 for every scheduled volume",
    )
    add_check(
        checks,
        "first_excluded_casimir",
        kappa_error <= TOLERANCE,
        kappa_error,
        f"kappa_C equals j_excluded(j_excluded+1) within {TOLERANCE}",
    )
    add_check(
        checks,
        "variational_energy_density",
        all(close(row["energy_bound_per_edge"], 2.0 * row["coupling_x"]) for row in local_rows),
        {"distinct_values": sorted({row["energy_bound_per_edge"] for row in local_rows})},
        "constant-state bound is E_0/|E| <= 2x",
    )

    grouped_bounds: dict[tuple[float, int, int], list[float]] = {}
    for row in local_rows:
        key = (row["coupling_x"], row["support_links"], row["cutoff_C"])
        grouped_bounds.setdefault(key, []).append(row["local_tail_bound"])
    maximum_volume_spread = max(max(values) - min(values) for values in grouped_bounds.values())
    add_check(
        checks,
        "local_bound_volume_invariance",
        maximum_volume_spread <= TOLERANCE,
        maximum_volume_spread,
        f"fixed-support tail bound is volume independent within {TOLERANCE}",
    )

    monotonic_failures: list[dict[str, Any]] = []
    for side in VOLUMES:
        for coupling in COUPLINGS:
            for support in SUPPORT_SIZES:
                values = [
                    row["local_tail_bound"]
                    for row in local_rows
                    if row["side_L"] == side
                    and row["coupling_x"] == coupling
                    and row["support_links"] == support
                ]
                if not all(right < left for left, right in zip(values, values[1:])):
                    monotonic_failures.append(
                        {"side_L": side, "coupling_x": coupling, "support_links": support}
                    )
    add_check(
        checks,
        "local_cutoff_monotonicity",
        not monotonic_failures,
        {"failures": monotonic_failures},
        "every fixed-volume, coupling, and support tail bound decreases strictly with C",
    )
    add_check(
        checks,
        "local_applicability_visible",
        0 < applicable < len(local_rows),
        {"attempted": len(local_rows), "applicable": applicable},
        "applicable and inapplicable observable rows are both explicit",
    )

    joint_rows: list[dict[str, Any]] = []
    for scale in JOINT_SCALES:
        coupling = float(scale**4)
        cutoff = scale**3
        ratio = cutoff * cutoff / coupling
        tail_bound = 2.0 * coupling / kappa(cutoff)
        joint_rows.append(
            {
                "scale_k": scale,
                "coupling_x": coupling,
                "cutoff_C": cutoff,
                "cutoff_squared_over_x": ratio,
                "local_tail_bound": tail_bound,
                "applicable": tail_bound < 1.0,
                "unit_observable_error_bound": observable_envelope(tail_bound),
            }
        )
    joint_ratio_error = max(
        abs(row["cutoff_squared_over_x"] - row["scale_k"] ** 2)
        for row in joint_rows
    )
    joint_tail_values = [row["local_tail_bound"] for row in joint_rows]
    joint_envelopes = [
        row["unit_observable_error_bound"]
        for row in joint_rows
        if row["unit_observable_error_bound"] is not None
    ]
    add_check(
        checks,
        "joint_cutoff_ratio_identity",
        joint_ratio_error <= TOLERANCE,
        joint_ratio_error,
        f"C_k^2/x_k = k^2 within {TOLERANCE}",
    )
    add_check(
        checks,
        "joint_schedule_convergence",
        all(right < left for left, right in zip(joint_tail_values, joint_tail_values[1:]))
        and len(joint_envelopes) > 1
        and all(right < left for left, right in zip(joint_envelopes, joint_envelopes[1:])),
        {
            "tail_bounds": joint_tail_values,
            "applicable_envelopes": joint_envelopes,
        },
        "joint-schedule tail and every applicable envelope decrease strictly",
    )

    obstruction_rows: list[dict[str, Any]] = []
    maximum_tail_series_error = 0.0
    maximum_energy_series_error = 0.0
    maximum_retained_reconstruction_error = 0.0
    cutoff_mismatches: list[dict[str, Any]] = []
    for q in PRODUCT_Q:
        energy_closed = electric_energy_per_loop(q)
        energy_direct = direct_energy_sum(q)
        maximum_energy_series_error = max(
            maximum_energy_series_error, abs(energy_closed - energy_direct)
        )
        for cutoff in PRODUCT_CUTOFFS:
            tail_closed = one_loop_tail(q, cutoff)
            tail_direct = direct_tail_sum(q, cutoff)
            maximum_tail_series_error = max(
                maximum_tail_series_error, abs(tail_closed - tail_direct)
            )
            for loops in PRODUCT_VOLUMES:
                retained = retained_norm_stable(q, cutoff, loops)
                discarded = discarded_norm_stable(q, cutoff, loops)
                retained_iterative = retained_norm_iterative(q, cutoff, loops)
                maximum_retained_reconstruction_error = max(
                    maximum_retained_reconstruction_error,
                    abs(retained - retained_iterative),
                    abs(discarded - (1.0 - retained_iterative)),
                )
                cutoff_formula = minimum_cutoff_formula(loops, q, EPSILON)
                cutoff_search = minimum_cutoff_search(loops, q, EPSILON)
                if cutoff_formula != cutoff_search:
                    cutoff_mismatches.append(
                        {
                            "q": q,
                            "loops_N": loops,
                            "formula": cutoff_formula,
                            "search": cutoff_search,
                        }
                    )
                obstruction_rows.append(
                    {
                        "q": q,
                        "cutoff_C": cutoff,
                        "loops_N": loops,
                        "one_loop_tail": tail_closed,
                        "retained_global_norm_sq": retained,
                        "discarded_global_norm_sq": discarded,
                        "electric_energy_per_loop": energy_closed,
                        "minimum_cutoff_epsilon_0_1": cutoff_formula,
                    }
                )

    expected_obstruction_rows = (
        len(PRODUCT_Q) * len(PRODUCT_CUTOFFS) * len(PRODUCT_VOLUMES)
    )
    add_check(
        checks,
        "global_obstruction_schedule_coverage",
        len(obstruction_rows) == expected_obstruction_rows == 180,
        {"rows": len(obstruction_rows), "expected": expected_obstruction_rows},
        "all 180 frozen product-family rows are present",
    )
    add_check(
        checks,
        "character_series_tail_identity",
        maximum_tail_series_error <= TOLERANCE,
        maximum_tail_series_error,
        f"direct and closed one-loop tails agree within {TOLERANCE}",
    )
    add_check(
        checks,
        "electric_energy_series_identity",
        maximum_energy_series_error <= TOLERANCE,
        maximum_energy_series_error,
        f"direct and closed electric energies agree within {TOLERANCE}",
    )
    add_check(
        checks,
        "global_norm_reconstruction",
        maximum_retained_reconstruction_error <= TOLERANCE,
        maximum_retained_reconstruction_error,
        f"iterative and stable global norms agree within {TOLERANCE}",
    )
    add_check(
        checks,
        "minimum_cutoff_identity",
        not cutoff_mismatches,
        {"mismatches": cutoff_mismatches},
        "closed and direct minimal cutoffs agree for every product row",
    )

    obstruction_monotonic_failures: list[dict[str, Any]] = []
    for q in PRODUCT_Q:
        for cutoff in PRODUCT_CUTOFFS:
            values = [
                row["discarded_global_norm_sq"]
                for row in obstruction_rows
                if row["q"] == q and row["cutoff_C"] == cutoff
            ]
            adjacent = list(zip(values, values[1:]))
            nondecreasing = all(right >= left for left, right in adjacent)
            strict_below_saturation = all(
                right > left
                for left, right in adjacent
                if left < 1.0 - TOLERANCE
            )
            if not (nondecreasing and strict_below_saturation):
                obstruction_monotonic_failures.append({"q": q, "cutoff_C": cutoff})
    add_check(
        checks,
        "global_discarded_mass_growth",
        not obstruction_monotonic_failures,
        {"failures": obstruction_monotonic_failures},
        "discarded global norm is nondecreasing in N and strict below numerical saturation",
    )

    firing = next(
        row
        for row in obstruction_rows
        if row["q"] == 0.5 and row["cutoff_C"] == 2 and row["loops_N"] == 512
    )
    add_check(
        checks,
        "global_uniformity_firing_control",
        firing["discarded_global_norm_sq"] > 0.999,
        firing,
        "q=1/2, C=2, N=512 has discarded global norm above 0.999",
    )

    passed = all(check["passed"] for check in checks)
    local_status = "PASS" if passed else "FAIL"
    record: dict[str, Any] = {
        "schema": "cassi.yang_mills_local_cutoff_density.v1",
        "status": local_status,
        "local_cutoff_status": local_status,
        "global_norm_uniformity": "EXCLUDED_BY_PRODUCT_FAMILY",
        "thermodynamic_limit_constructed": False,
        "continuum_hypotheses_present": False,
        "clay_verdict": "NULL",
        "inputs": {
            "protocol": {"path": display_path(PROTOCOL), "sha256": sha256(PROTOCOL)},
            "primary_source": {"path": display_path(SOURCE), "sha256": sha256(SOURCE)},
        },
        "schedule": {
            "volumes_L": list(VOLUMES),
            "couplings_x": list(COUPLINGS),
            "support_sizes": list(SUPPORT_SIZES),
            "cutoffs_C": list(CUTOFFS),
            "joint_scales_k": list(JOINT_SCALES),
            "product_q": list(PRODUCT_Q),
            "product_cutoffs_C": list(PRODUCT_CUTOFFS),
            "product_volumes_N": list(PRODUCT_VOLUMES),
            "epsilon": EPSILON,
            "series_terminal": SERIES_TERMINAL,
        },
        "local_volume_rows": local_rows,
        "local_summary": {
            "attempted": len(local_rows),
            "applicable": applicable,
            "maximum_volume_spread": maximum_volume_spread,
        },
        "joint_cutoff_rows": joint_rows,
        "global_obstruction": {
            "rows": obstruction_rows,
            "firing_control": firing,
            "maximum_tail_series_error": maximum_tail_series_error,
            "maximum_energy_series_error": maximum_energy_series_error,
            "maximum_retained_reconstruction_error": maximum_retained_reconstruction_error,
        },
        "checks": checks,
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
        "claim_boundary": (
            "The result proves a volume-uniform fixed-support character-projection "
            "bound at fixed coupling and proves that electric-energy-density control "
            "alone cannot give volume-uniform whole-wavefunction truncation. It does "
            "not construct a thermodynamic or continuum state, prove clustering, or "
            "establish a regulator-independent mass gap."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    if not passed:
        failed = [check["name"] for check in checks if not check["passed"]]
        raise RuntimeError(f"local cutoff verification failed: {failed}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    result = run(arguments.output, arguments.replace)
    local = result["local_summary"]
    firing = result["global_obstruction"]["firing_control"]
    print(
        f"status={result['local_cutoff_status']} clay={result['clay_verdict']} "
        f"checks={result['checks_passed']}/{result['checks_total']}"
    )
    print(
        f"local={local['applicable']}/{local['attempted']} "
        f"volume_spread={local['maximum_volume_spread']:.3e} "
        f"firing_discarded={firing['discarded_global_norm_sq']:.12f}"
    )


if __name__ == "__main__":
    main()
