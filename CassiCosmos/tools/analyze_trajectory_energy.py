"""Analyze the registered Gaussian energy/seed trajectory scan.

The per-arm radial statistic is the one registered in
``research/matter_formation/trajectory_energy_prereg.md``. This wrapper adds the
factorial speed/seed comparison and writes one summary without relying on the
presentation layer.

Run from the CassiCosmos repository root::

    python tools/analyze_trajectory_energy.py
    python tools/analyze_trajectory_energy.py --run _diag/matter_formation/energy_gaussian_s20260910_v0p0
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_trajectory_attractor import (  # pyright: ignore[reportMissingImports]  # noqa: E402
    AnalysisFailure,
    _json_safe,
    analyze_arm,
)

PREREG = "research/matter_formation/trajectory_energy_prereg.md"
DIAG_ROOT = Path("_diag/matter_formation")
SUMMARY_PATH = DIAG_ROOT / "energy_gaussian_summary.json"
EXPECTED_ARMS = 8
EXPECTED_SPEEDS = (0.0, 0.5, 1.0, 2.0)
EXPECTED_SEEDS = (20260910, 20260911)
RIDGE_MATCH_TOLERANCE = 0.15

EXPECTED_ENGINE: dict[str, Any] = {
    "N_particles": 8192,
    "grid_N": 64,
    "dt": 0.001,
    "xi": 17.94427191,
    "softening": 0.1,
    "cluster_radius": 25.0,
    "cluster_separation": 0.0,
    "num_clusters": 1,
    "box_scale": 1.0,
    "initial_condition": 1,
    "initial_arrangement": 2,
    "initial_motion": 4,
    "initial_total_mass": 1000.0,
    "initial_radius_fraction": 0.9,
    "gravity_mode": 5,
    "gridless_physics": True,
    "meshless_mode": True,
    "meshless_gravity": True,
    "freeze_field": True,
    "field_attractor_init": True,
    "source_strength": 0.0,
    "river_calibrate_gn": False,
    "particle_merge": False,
    "black_holes_enabled": False,
    "bh_accretion": False,
    "dual_grid": False,
    "tree_cadence": 1,
    "trajectory_enabled": True,
}


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and bool(
            np.isclose(float(actual), float(expected), rtol=1.0e-7, atol=1.0e-9)
        )
    return actual == expected


def _verify_config(receipt: dict[str, Any]) -> None:
    engine = receipt.get("engine")
    if not isinstance(engine, dict):
        raise AnalysisFailure("receipt has no engine configuration")
    for key, expected in EXPECTED_ENGINE.items():
        if key not in engine or not _same_value(engine[key], expected):
            raise AnalysisFailure(
                f"engine.{key}={engine.get(key)!r}, expected {expected!r}"
            )
    if int(receipt.get("accepted_steps", -1)) != 100_000:
        raise AnalysisFailure("accepted step count does not match the frozen 100000")
    for key, expected in {
        "recorder_enabled": True,
        "tracer_count": 4096,
        "sample_stride": 400,
        "sample_capacity": 256,
        "event_capacity": 65536,
    }.items():
        if not _same_value(receipt.get(key), expected):
            raise AnalysisFailure(
                f"receipt.{key}={receipt.get(key)!r}, expected {expected!r}"
            )
    field_control = receipt.get("field_control")
    if not isinstance(field_control, dict) or field_control.get("field_attractor_init") is not True:
        raise AnalysisFailure("field-control attractor initialization is missing")


def _ridge_positions(arm: dict[str, Any]) -> list[float]:
    return [float(ridge["u"]) for ridge in arm.get("ridges", [])]


def _match_count(left: list[float], right: list[float]) -> int:
    used: set[int] = set()
    count = 0
    for value in left:
        best = -1
        best_delta = RIDGE_MATCH_TOLERANCE
        for index, target in enumerate(right):
            if index in used:
                continue
            delta = abs(value - target)
            if delta <= best_delta:
                best = index
                best_delta = delta
        if best >= 0:
            used.add(best)
            count += 1
    return count


def _ridge_lists_differ(left: list[float], right: list[float]) -> bool:
    return _match_count(left, right) < max(len(left), len(right))


def _run_metadata(run_dir: Path, arm: dict[str, Any]) -> dict[str, Any]:
    receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
    _verify_config(receipt)
    engine = receipt["engine"]
    speed = float(engine["initial_speed"])
    seed = int(receipt["seed"])
    if seed not in EXPECTED_SEEDS:
        raise AnalysisFailure(f"seed {seed} is outside the frozen factorial")
    if not any(np.isclose(speed, expected) for expected in EXPECTED_SPEEDS):
        raise AnalysisFailure(f"speed {speed} is outside the frozen factorial")
    if not _same_value(arm.get("ic_index"), 1):
        raise AnalysisFailure("analyzed arm is not Gaussian")
    arm["seed"] = seed
    arm["initial_motion"] = int(engine["initial_motion"])
    arm["initial_speed"] = speed
    arm["kinetic_scale_v2"] = speed * speed
    arm["ridge_positions"] = _ridge_positions(arm)
    return arm


def _analyze_run(run_dir: Path) -> dict[str, Any]:
    try:
        arm = analyze_arm(run_dir, strict=False)
        arm = _run_metadata(run_dir, arm)
        arm["status"] = "OK"
        (run_dir / "analysis.json").write_text(
            json.dumps(_json_safe(arm), indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return arm
    except (AnalysisFailure, KeyError, OSError, ValueError) as exc:
        return {"run_dir": str(run_dir), "status": "FAIL", "error": str(exc)}


def _group_summary(arms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[float, dict[int, dict[str, Any]]] = defaultdict(dict)
    for arm in arms:
        if arm.get("status") == "OK":
            grouped[float(arm["initial_speed"])][int(arm["seed"])] = arm
    result: list[dict[str, Any]] = []
    for speed in EXPECTED_SPEEDS:
        by_seed = grouped.get(speed, {})
        seed_rows: list[dict[str, Any]] = []
        for seed in EXPECTED_SEEDS:
            arm = by_seed.get(seed)
            if arm is None:
                seed_rows.append({"seed": seed, "status": "MISSING"})
                continue
            seed_rows.append(
                {
                    "seed": seed,
                    "status": "OK",
                    "shell_verdict": arm["shell_verdict"],
                    "ridge_count": int(arm["ridge_count"]),
                    "ridge_positions": arm["ridge_positions"],
                    "late_ridge_counts": arm["late_slot_ridge_counts"],
                    "r50_late_mean": arm["r50_late_mean"],
                    "r50_late_std": arm["r50_late_std"],
                    "concentration_r90_over_r50": arm[
                        "concentration_r90_over_r50"
                    ],
                    "kinetic_scale_v2": arm["kinetic_scale_v2"],
                }
            )
        result.append(
            {
                "speed": speed,
                "kinetic_scale_v2": speed * speed,
                "seeds": seed_rows,
            }
        )
    return result


def _compare_groups(groups: list[dict[str, Any]]) -> dict[str, Any]:
    by_speed = {float(group["speed"]): group for group in groups}
    baseline = by_speed.get(0.0)
    structural_ok = all(
        seed.get("status") == "OK"
        for group in groups
        for seed in group["seeds"]
    )
    for group in groups:
        rows = group["seeds"]
        ok_rows = [row for row in rows if row.get("status") == "OK"]
        if len(ok_rows) == 2:
            group["seed_stable"] = (
                ok_rows[0]["shell_verdict"] == ok_rows[1]["shell_verdict"]
                and _match_count(
                    ok_rows[0]["ridge_positions"], ok_rows[1]["ridge_positions"]
                )
                == max(
                    len(ok_rows[0]["ridge_positions"]),
                    len(ok_rows[1]["ridge_positions"]),
                )
            )
            group["seed_status"] = (
                "seed-stable" if group["seed_stable"] else "seed-sensitive"
            )
        else:
            group["seed_stable"] = False
            group["seed_status"] = "missing"
    support_groups: list[float] = []
    if structural_ok and baseline is not None:
        base_by_seed = {int(row["seed"]): row for row in baseline["seeds"]}
        for group in groups:
            speed = float(group["speed"])
            if speed <= 0.0:
                continue
            qualifying = True
            for row in group["seeds"]:
                base = base_by_seed[int(row["seed"])]
                qualifying = qualifying and (
                    row["shell_verdict"] == "SHELL_SUPPORTS"
                    and _ridge_lists_differ(
                        row["ridge_positions"], base["ridge_positions"]
                    )
                )
            group["differs_from_zero_control"] = qualifying
            if qualifying:
                support_groups.append(speed)
    else:
        for group in groups:
            group["differs_from_zero_control"] = False
    seed_sensitive_nonzero = any(
        group.get("seed_status") == "seed-sensitive"
        and float(group["speed"]) > 0.0
        for group in groups
    )
    if not structural_ok:
        verdict = "INCONCLUSIVE"
        reason = "one or more frozen factorial arms failed structural analysis"
    elif support_groups:
        verdict = "SUPPORTS"
        reason = (
            "both seeds show qualifying nonzero-speed shell profiles that differ "
            f"from their zero-speed controls at speeds {support_groups}"
        )
    elif seed_sensitive_nonzero:
        verdict = "INCONCLUSIVE"
        reason = "a nonzero-speed group is seed-sensitive, preventing the registered comparison"
    else:
        verdict = "DOES NOT EMERGE"
        reason = "no nonzero-speed group satisfies the two-seed shell criterion"
    return {
        "structural_ok": structural_ok,
        "support_speeds": support_groups,
        "verdict": verdict,
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        type=Path,
        action="append",
        default=None,
        help="energy arm directory; repeatable (default: discover registered names)",
    )
    parser.add_argument("--out", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args(argv)
    run_dirs = (
        args.run
        if args.run
        else sorted(
            path
            for path in DIAG_ROOT.glob("energy_gaussian_s*_v*p*")
            if path.is_dir()
        )
    )
    if not run_dirs:
        print("no energy arm directories found", file=sys.stderr)
        return 1
    arms: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        if not (run_dir / "receipt.json").is_file():
            arm = {"run_dir": str(run_dir), "status": "MISSING"}
        else:
            arm = _analyze_run(run_dir)
        arms.append(arm)
        if arm.get("status") == "OK":
            print(
                f"{run_dir}: seed={arm['seed']} speed={arm['initial_speed']:.2f} "
                f"ridges={arm['ridge_count']} {arm['ridge_positions']} "
                f"late={arm['late_slot_ridge_counts']} {arm['shell_verdict']}"
            )
        else:
            print(f"{run_dir}: {arm['status']} — {arm.get('error', '')}")
    groups = _group_summary(arms)
    comparison = _compare_groups(groups)
    summary = {
        "schema": "cassi.trajectory-energy-summary.v1",
        "prereg": PREREG,
        "registered_arms": EXPECTED_ARMS,
        "analyzed_arms": len(arms),
        "arms": arms,
        "speed_groups": groups,
        **comparison,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(_json_safe(summary), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nVERDICT: {comparison['verdict']} — {comparison['reason']}")
    print(f"wrote {args.out}")
    return 0 if comparison["verdict"] != "INCONCLUSIVE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
