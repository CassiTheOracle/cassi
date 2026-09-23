#!/usr/bin/env python3
"""Measure target-independent morphology coordinates from trajectory snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from cassi_morphology_observables import morphology_atoms


def _read_snapshot(root: Path, slot: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
    slots = int(receipt["sample_slots"])
    tracers = int(receipt["tracer_count"])
    if slot < 0:
        slot += slots
    if slot < 0 or slot >= slots:
        raise ValueError(f"snapshot slot {slot} is outside 0..{slots - 1}")
    shape = (slots, tracers, 4)
    position = np.fromfile(root / "history_pos.bin", dtype="<f4").reshape(shape)[slot]
    velocity = np.fromfile(root / "history_vel.bin", dtype="<f4").reshape(shape)[slot, :, :3]
    center = np.asarray(receipt["engine"]["window_center"], dtype=np.float64)
    relative = position[:, :3].astype(np.float64) - center
    mass = position[:, 3].astype(np.float64)
    radius = np.linalg.norm(relative, axis=1)
    live = (mass > 0.0) & (radius > 1e-9)
    if int(np.count_nonzero(live)) < 16:
        raise ValueError(f"snapshot {slot} has fewer than sixteen valid tracers")
    return relative[live], velocity[live].astype(np.float64), mass[live], receipt


def measure(root: Path, *, slots: Sequence[int]) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rows: list[dict[str, Any]] = []
    for slot in slots:
        position, velocity, mass, receipt = _read_snapshot(root, int(slot))
        atoms = morphology_atoms(position, velocity, mass)
        rows.append(
            {
                "slot": int(slot if slot >= 0 else int(receipt["sample_slots"]) + slot),
                "step": int(np.fromfile(root / "sample_steps.bin", dtype="<u4")[slot]),
                "live_tracers": len(position),
                "coordinates": {name: float(np.mean(value)) for name, value in atoms.items()},
            }
        )
    return {"schema": "cassifi.morphology-observable-measurement.v1", "root": str(root), "samples": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--slots", nargs="+", type=int, default=(1, 125, -2))
    args = parser.parse_args(argv)
    result = {str(root): measure(root, slots=args.slots) for root in args.roots}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
