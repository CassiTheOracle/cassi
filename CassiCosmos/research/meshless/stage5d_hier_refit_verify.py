#!/usr/bin/env python
"""G70/G71 hierarchical retained-moment identity and queued-cost gates."""

import base64
import json
import math
import statistics
import sys

import numpy as np


def _gradient(payload: str, count: int) -> np.ndarray:
    values = np.frombuffer(base64.b64decode(payload), dtype=np.float32)
    if values.size < count * 4:
        raise ValueError(f"gradient has {values.size} floats; expected {count * 4}")
    return values[: count * 4].reshape(count, 4)[:, :3].astype(np.float64)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "_diag/tree_hier_refit_gpu.json"
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)

    count = int(data["target_count"])
    hierarchical = _gradient(data["hier_gradient_b64"], count)
    fresh = _gradient(data["fresh_gradient_b64"], count)
    finite = bool(np.isfinite(hierarchical).all() and np.isfinite(fresh).all())

    reference_magnitude = np.linalg.norm(fresh, axis=1)
    keep = reference_magnitude > 1e-8
    relative = np.linalg.norm(hierarchical - fresh, axis=1) / np.maximum(
        reference_magnitude, 1e-8
    )
    median = float(np.median(relative[keep])) if keep.any() else math.inf
    p99 = float(np.percentile(relative[keep], 99)) if keep.any() else math.inf
    maximum = float(np.max(relative[keep])) if keep.any() else math.inf
    opposite = (
        float(np.mean(np.einsum("ij,ij->i", hierarchical[keep], fresh[keep]) < 0.0))
        if keep.any()
        else 1.0
    )

    # The receipt's "centers" flag compares the complete active ncf bytes,
    # which G70 explicitly freezes alongside srcorder and nr.
    structure = all(
        bool(data[key])
        for key in (
            "retained_node_count_identical",
            "retained_order_identical",
            "retained_ranges_identical",
            "retained_centers_identical",
        )
    )
    g70 = (
        structure
        and finite
        and math.isfinite(median)
        and median <= 1e-6
        and p99 <= 1e-5
        and maximum <= 1e-4
        and opposite == 0.0
    )

    batch_size = int(data["batch_size"])
    warmups = int(data["warmups"])
    repetitions = int(data["repetitions"])
    full_batch = [float(value) for value in data["full_batch_us"]]
    hier_batch = [float(value) for value in data["hier_batch_us"]]
    if len(full_batch) != len(hier_batch) or not full_batch:
        raise ValueError("fresh/refit timing arrays must be non-empty and paired")
    timing_contract = (
        batch_size == 32
        and warmups == 3
        and repetitions == 11
        and len(full_batch) == repetitions
    )
    full_per_prepare = [value / batch_size for value in full_batch]
    hier_per_prepare = [value / batch_size for value in hier_batch]
    full_median = statistics.median(full_per_prepare)
    hier_median = statistics.median(hier_per_prepare)
    ratio = hier_median / full_median if full_median > 0.0 else math.inf
    every_pair_faster = all(
        hier < full for hier, full in zip(hier_per_prepare, full_per_prepare)
    )
    g71 = (
        timing_contract
        and math.isfinite(ratio)
        and ratio <= 0.25
        and every_pair_faster
    )

    print("=== G70: hierarchical retained-moment identity ===")
    print(
        "retained structure: count=%s order=%s ranges=%s centers=%s"
        % (
            data["retained_node_count_identical"],
            data["retained_order_identical"],
            data["retained_ranges_identical"],
            data["retained_centers_identical"],
        )
    )
    print(
        "nodes: retained=%d hierarchical=%d fresh=%d  dispatches: hierarchical=%d fresh=%d"
        % (
            data["retained_node_count"],
            data["hier_node_count"],
            data["fresh_node_count"],
            data["hier_dispatches"],
            data["full_dispatches"],
        )
    )
    print(
        "force relative difference: median=%.3e p99=%.3e max=%.3e opposite=%.6f finite=%s"
        % (median, p99, maximum, opposite, finite)
    )
    print("fresh raw slots match retained: %s" % data["fresh_raw_slots_identical"])
    print("G70: %s" % ("PASS" if g70 else "FAIL"))

    print("=== G71: queued preparation cost ===")
    print("fresh us/preparation: %s  median=%.3f" % (full_per_prepare, full_median))
    print("refit us/preparation: %s  median=%.3f" % (hier_per_prepare, hier_median))
    print(
        "refit/fresh median ratio=%.6f threshold<=0.25 every_pair_faster=%s "
        "batch=%d warmups=%d repetitions=%d contract=%s"
        % (
            ratio, every_pair_faster, batch_size, warmups, repetitions,
            timing_contract,
        )
    )
    print("G71: %s" % ("PASS" if g71 else "FAIL"))
    raise SystemExit(0 if g70 and g71 else 1)


if __name__ == "__main__":
    main()
