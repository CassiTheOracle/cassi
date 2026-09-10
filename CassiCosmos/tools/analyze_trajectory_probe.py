#!/usr/bin/env python3
"""Analyze raw CassiCosmos trajectory-probe artifacts.

Usage:
    python tools/analyze_trajectory_probe.py _diag/matter_formation/trajectory_shell

The script treats the Godot receipt and binary payloads as the evidence source.
It writes analysis.json beside them and exits nonzero only for an artifact or
invariant failure. A scientific negative result is a successful analysis.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

EVENT_DTYPE = np.dtype(
    [
        ("step", "<u4"),
        ("source", "<u4"),
        ("survivor", "<u4"),
        ("flags", "<u4"),
        ("source_pos", "<f4", (4,)),
        ("source_vel", "<f4", (4,)),
        ("survivor_pos", "<f4", (4,)),
        ("survivor_vel", "<f4", (4,)),
    ],
    align=False,
)
assert EVENT_DTYPE.itemsize == 80


class AnalysisFailure(Exception):
    """A malformed receipt or raw artifact."""


def _number(receipt: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = receipt.get(key, default)
    if isinstance(value, bool):
        raise AnalysisFailure(f"{key} is boolean")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalysisFailure(f"{key} is not numeric") from exc
    if not np.isfinite(result):
        raise AnalysisFailure(f"{key} is not finite")
    return result


def _integer(receipt: dict[str, Any], key: str, default: int = 0) -> int:
    value = receipt.get(key, default)
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise AnalysisFailure(f"{key} is not integral") from exc
    return result


def _read_exact(run_dir: Path, name: str, dtype: np.dtype[Any], count: int) -> np.ndarray:
    path = run_dir / name
    if not path.is_file():
        raise AnalysisFailure(f"missing {name}")
    expected_bytes = int(np.dtype(dtype).itemsize) * count
    actual_bytes = path.stat().st_size
    if actual_bytes != expected_bytes:
        raise AnalysisFailure(
            f"{name} has {actual_bytes} bytes; expected {expected_bytes}"
        )
    values = np.fromfile(path, dtype=dtype)
    if values.size != count:
        raise AnalysisFailure(f"{name} has {values.size} records; expected {count}")
    return values


def _json_number(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def _crossings(radius: np.ndarray, boundary: float) -> dict[str, int]:
    if radius.shape[0] < 2:
        return {"inward": 0, "outward": 0}
    previous = radius[:-1]
    current = radius[1:]
    valid = np.isfinite(previous) & np.isfinite(current)
    inward = valid & (previous > boundary) & (current <= boundary)
    outward = valid & (previous < boundary) & (current >= boundary)
    return {"inward": int(inward.sum()), "outward": int(outward.sum())}


def _turnarounds(radial_velocity: np.ndarray) -> dict[str, int]:
    if radial_velocity.shape[0] < 2:
        return {"inward_to_outward": 0, "outward_to_inward": 0}
    previous = radial_velocity[:-1]
    current = radial_velocity[1:]
    valid = np.isfinite(previous) & np.isfinite(current)
    inward_to_outward = valid & (previous < 0.0) & (current >= 0.0)
    outward_to_inward = valid & (previous > 0.0) & (current <= 0.0)
    return {
        "inward_to_outward": int(inward_to_outward.sum()),
        "outward_to_inward": int(outward_to_inward.sum()),
    }


def _component_sizes(edges: list[tuple[int, int]]) -> list[int]:
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for source, survivor in edges:
        union(source, survivor)
    sizes: dict[int, int] = {}
    for node in parent:
        root = find(node)
        sizes[root] = sizes.get(root, 0) + 1
    return sorted(sizes.values(), reverse=True)


def _ancestry_depth(edges: list[tuple[int, int]]) -> tuple[int, bool]:
    next_parent: dict[int, int] = {}
    cyclic = False
    for source, survivor in edges:
        existing = next_parent.get(source)
        if existing is not None and existing != survivor:
            cyclic = True
        next_parent[source] = survivor
    max_depth = 0
    for start in next_parent:
        current = start
        seen: set[int] = set()
        depth = 0
        while current in next_parent:
            if current in seen:
                cyclic = True
                break
            seen.add(current)
            current = next_parent[current]
            depth += 1
        max_depth = max(max_depth, depth)
    return max_depth, cyclic


def _shell_candidates(
    occupancy: np.ndarray,
    initial_occupancy: np.ndarray,
    steps: np.ndarray,
    sample_stride: int,
) -> list[dict[str, Any]]:
    if occupancy.size == 0:
        return []
    live_counts = np.maximum(occupancy.sum(axis=1), 1)
    initial_live = max(int(initial_occupancy.sum()), 1)
    fractions = occupancy / live_counts[:, None]
    baseline = initial_occupancy / initial_live
    denominator = np.maximum(baseline, 1.0 / initial_live)
    contrast = fractions / denominator[None, :]
    local_max = np.zeros_like(contrast, dtype=bool)
    if contrast.shape[1] >= 3:
        local_max[:, 1:-1] = (
            (contrast[:, 1:-1] > contrast[:, :-2])
            & (contrast[:, 1:-1] >= contrast[:, 2:])
            & (contrast[:, 1:-1] > 1.5)
        )
    candidates: list[dict[str, Any]] = []
    for bin_index in range(contrast.shape[1]):
        start = None
        for slot in range(contrast.shape[0]):
            contiguous = (
                slot > 0
                and int(steps[slot]) - int(steps[slot - 1]) == sample_stride
            )
            active = bool(local_max[slot, bin_index])
            if active and start is None:
                start = slot
            elif active and start is not None and contiguous:
                continue
            elif active:
                start = slot
            elif start is not None:
                length = slot - start
                if length >= 3:
                    peak_slot = start + int(np.argmax(contrast[start:slot, bin_index]))
                    candidates.append(
                        {
                            "bin": bin_index,
                            "start_step": int(steps[start]),
                            "end_step": int(steps[slot - 1]),
                            "peak_step": int(steps[peak_slot]),
                            "contrast": float(contrast[peak_slot, bin_index]),
                            "persistence_slots": length,
                        }
                    )
                start = None
        if start is not None:
            length = contrast.shape[0] - start
            if length >= 3:
                peak_slot = start + int(np.argmax(contrast[start:, bin_index]))
                candidates.append(
                    {
                        "bin": bin_index,
                        "start_step": int(steps[start]),
                        "end_step": int(steps[-1]),
                        "peak_step": int(steps[peak_slot]),
                        "contrast": float(contrast[peak_slot, bin_index]),
                        "persistence_slots": length,
                    }
                )
    return candidates


def analyze(run_dir: Path, bins: int) -> tuple[dict[str, Any], int]:
    receipt_path = run_dir / "receipt.json"
    if not receipt_path.is_file():
        raise AnalysisFailure("missing receipt.json")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisFailure(f"invalid receipt.json: {exc}") from exc
    if receipt.get("schema") != "cassi.trajectory-probe.v1":
        raise AnalysisFailure("unsupported trajectory receipt schema")

    tracer_count = _integer(receipt, "tracer_count")
    sample_slots = _integer(receipt, "sample_slots")
    sample_total = _integer(receipt, "sample_total")
    sample_capacity = _integer(receipt, "sample_capacity")
    sample_stride = _integer(receipt, "sample_stride")
    event_total = _integer(receipt, "event_total")
    event_stored = _integer(receipt, "event_records_stored")
    event_capacity = _integer(receipt, "event_capacity")
    particle_count = _integer(receipt, "N_particles")
    accepted_steps = _integer(receipt, "accepted_steps")
    inner_radius = _number(receipt, "inner_radius")
    outer_radius = _number(receipt, "outer_radius")
    initial_total_mass = _number(receipt, "initial_total_mass")
    final_total_mass = _number(receipt, "final_total_mass")
    sample_overflow = _integer(receipt, "sample_overflow")
    event_overflow = _integer(receipt, "event_overflow")

    if tracer_count < 1 or sample_slots < 1 or sample_slots > sample_capacity:
        raise AnalysisFailure("invalid sample dimensions in receipt")
    if sample_total < sample_slots or event_total < event_stored:
        raise AnalysisFailure("receipt counters are internally inconsistent")
    if event_stored > event_capacity:
        raise AnalysisFailure("stored events exceed event capacity")
    if bins < 4:
        raise AnalysisFailure("bin count must be at least four")

    ids = _read_exact(run_dir, "tracer_ids.bin", np.dtype("<u4"), tracer_count)
    sample_steps = _read_exact(run_dir, "sample_steps.bin", np.dtype("<u4"), sample_slots)
    history_pos = _read_exact(
        run_dir, "history_pos.bin", np.dtype("<f4"), sample_slots * tracer_count * 4
    ).reshape(sample_slots, tracer_count, 4)
    history_vel = _read_exact(
        run_dir, "history_vel.bin", np.dtype("<f4"), sample_slots * tracer_count * 4
    ).reshape(sample_slots, tracer_count, 4)
    initial_tracers = _read_exact(
        run_dir, "initial_tracers.bin", np.dtype("<f4"), tracer_count * 4
    ).reshape(tracer_count, 4)
    final_tracers = _read_exact(
        run_dir, "final_tracers.bin", np.dtype("<f4"), tracer_count * 4
    ).reshape(tracer_count, 4)
    events = _read_exact(run_dir, "events.bin", EVENT_DTYPE, event_stored)

    hard_failures: list[str] = []
    if not np.array_equal(np.sort(ids), ids):
        hard_failures.append("tracer IDs are not strictly increasing")
    if ids.size and (int(ids.min()) < 0 or int(ids.max()) >= particle_count):
        hard_failures.append("tracer ID outside particle range")
    if np.unique(ids).size != ids.size:
        hard_failures.append("tracer IDs are not unique")
    for name, values in (
        ("sample_steps", sample_steps),
        ("history_pos", history_pos),
        ("history_vel", history_vel),
        ("initial_tracers", initial_tracers),
        ("final_tracers", final_tracers),
    ):
        if not np.isfinite(values).all():
            hard_failures.append(f"{name} contains nonfinite values")
    if not np.all(np.diff(sample_steps) >= 0) and sample_total <= sample_capacity:
        hard_failures.append("sample steps are not chronological in an unwrapped ring")
    if sample_overflow != 0:
        hard_failures.append(f"sample ring overflow={sample_overflow}")
    if event_overflow != 0:
        hard_failures.append(f"event buffer overflow={event_overflow}")
    if event_total != event_stored:
        hard_failures.append(
            f"event ledger truncated: total={event_total} stored={event_stored}"
        )

    order = np.argsort(sample_steps, kind="stable")
    ordered_steps = sample_steps[order]
    ordered_pos = history_pos[order]
    ordered_vel = history_vel[order]
    center = np.asarray(receipt.get("window_center", [0.0, 0.0, 0.0]), dtype=np.float64)
    if center.shape != (3,) or not np.isfinite(center).all():
        hard_failures.append("window center is invalid")
        center = np.zeros(3, dtype=np.float64)
    radius = np.linalg.norm(ordered_pos[:, :, :3] - center, axis=2)
    initial_radius = np.linalg.norm(initial_tracers[:, :3] - center, axis=1)
    final_radius = np.linalg.norm(final_tracers[:, :3] - center, axis=1)
    radial_velocity = ordered_vel[:, :, 3]
    alive = ordered_pos[:, :, 3] > 0.0
    finite_alive = np.isfinite(ordered_pos).all(axis=2) & np.isfinite(ordered_vel).all(axis=2)

    finite_fraction = float(finite_alive.mean()) if finite_alive.size else 0.0
    live_fraction = float(alive.mean()) if alive.size else 0.0
    if finite_fraction < 1.0:
        hard_failures.append(f"finite trajectory fraction={finite_fraction:.6f}")

    maximum_radius = float(np.nanmax(radius)) if radius.size else 0.0
    radial_limit = max(maximum_radius * 1.05, outer_radius * 1.05, 1.0e-6)
    edges = np.linspace(0.0, radial_limit, bins + 1)
    occupancy = np.zeros((sample_slots, bins), dtype=np.int64)
    for slot in range(sample_slots):
        valid = alive[slot] & np.isfinite(radius[slot])
        occupancy[slot], _ = np.histogram(radius[slot, valid], bins=edges)
    initial_valid = initial_tracers[:, 3] > 0.0
    initial_occupancy, _ = np.histogram(initial_radius[initial_valid], bins=edges)
    shell_candidates = _shell_candidates(
        occupancy, initial_occupancy, ordered_steps, sample_stride
    )

    crossing_inner = _crossings(radius, inner_radius)
    crossing_outer = _crossings(radius, outer_radius)
    turnaround = _turnarounds(radial_velocity)

    mass_relative_error = abs(final_total_mass - initial_total_mass) / max(initial_total_mass, 1.0e-30)
    if mass_relative_error > 1.0e-4:
        hard_failures.append(f"mass closure relative error={mass_relative_error:.6e}")

    edges_graph: list[tuple[int, int]] = []
    event_state_failures = 0
    for event in events:
        source = int(event["source"])
        survivor = int(event["survivor"])
        if int(event["flags"]) != 1 or source >= particle_count or survivor >= particle_count:
            event_state_failures += 1
            continue
        if source <= survivor:
            event_state_failures += 1
        source_pos = event["source_pos"]
        source_vel = event["source_vel"]
        survivor_pos = event["survivor_pos"]
        survivor_vel = event["survivor_vel"]
        if not (
            np.isfinite(source_pos).all()
            and np.isfinite(source_vel).all()
            and np.isfinite(survivor_pos).all()
            and np.isfinite(survivor_vel).all()
            and source_pos[3] > 0.0
            and survivor_pos[3] > source_pos[3]
        ):
            event_state_failures += 1
        if int(event["step"]) > accepted_steps:
            event_state_failures += 1
        edges_graph.append((source, survivor))
    if event_state_failures:
        hard_failures.append(f"invalid event state records={event_state_failures}")
    maximum_depth, graph_cycle = _ancestry_depth(edges_graph)
    if graph_cycle:
        hard_failures.append("merge ancestry graph contains a cycle or conflicting parent")
    component_sizes = _component_sizes(edges_graph)

    shell_verdict = "SUPPORTS" if shell_candidates else "DOES NOT EMERGE"
    ancestry_verdict = "SUPPORTS" if edges_graph else "DOES NOT EMERGE"
    overall_verdict = "FAIL" if hard_failures else shell_verdict
    analysis: dict[str, Any] = {
        "schema": "cassi.trajectory-analysis.v1",
        "mode": receipt.get("mode"),
        "run_dir": str(run_dir),
        "hard_failures": hard_failures,
        "verdict": overall_verdict,
        "shell_verdict": shell_verdict if not hard_failures else "FAIL",
        "ancestry_verdict": ancestry_verdict if not hard_failures else "FAIL",
        "sample_steps": [int(step) for step in ordered_steps],
        "sample_count_stored": sample_slots,
        "sample_count_total": sample_total,
        "sample_overflow": sample_overflow,
        "radial_bins": {
            "count": bins,
            "edges": edges.tolist(),
            "initial_occupancy": initial_occupancy.tolist(),
            "final_occupancy": occupancy[order[-1]].tolist(),
            "maximum_contrast": float(
                np.max(
                    occupancy / np.maximum(occupancy.sum(axis=1), 1)[:, None]
                    / np.maximum(initial_occupancy / max(int(initial_occupancy.sum()), 1), 1.0 / max(int(initial_occupancy.sum()), 1))[None, :]
                )
            ),
        },
        "shell_candidates": shell_candidates,
        "shell_boundaries": {
            "inner": inner_radius,
            "outer": outer_radius,
            "inner_crossings": crossing_inner,
            "outer_crossings": crossing_outer,
        },
        "turnarounds": turnaround,
        "trajectory_health": {
            "finite_sample_fraction": finite_fraction,
            "alive_sample_fraction": live_fraction,
            "initial_tracer_live_count": int(initial_valid.sum()),
            "final_tracer_live_count": int((final_tracers[:, 3] > 0.0).sum()),
        },
        "mass_closure": {
            "initial_total_mass": initial_total_mass,
            "final_total_mass": final_total_mass,
            "relative_error": mass_relative_error,
        },
        "ancestry": {
            "event_total": event_total,
            "event_records_stored": event_stored,
            "unique_sources": len({source for source, _ in edges_graph}),
            "unique_survivors": len({survivor for _, survivor in edges_graph}),
            "maximum_depth": maximum_depth,
            "component_sizes": component_sizes,
            "event_state_failures": event_state_failures,
        },
    }
    output_path = run_dir / "analysis.json"
    output_path.write_text(json.dumps(analysis, indent=2, default=_json_number) + "\n", encoding="utf-8")
    return analysis, 1 if hard_failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--bins", type=int, default=32)
    args = parser.parse_args(argv)
    try:
        analysis, code = analyze(args.run_dir, args.bins)
    except (AnalysisFailure, OSError, ValueError) as exc:
        print(f"[trajectory-analysis] FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        "[trajectory-analysis] %s shell=%s ancestry=%s samples=%d events=%d"
        % (
            analysis["verdict"],
            analysis["shell_verdict"],
            analysis["ancestry_verdict"],
            analysis["sample_count_stored"],
            analysis["ancestry"]["event_records_stored"],
        )
    )
    if analysis["hard_failures"]:
        for failure in analysis["hard_failures"]:
            print(f"[trajectory-analysis] FAIL: {failure}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
