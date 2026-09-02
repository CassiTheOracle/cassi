#!/usr/bin/env python
"""G63 persistent tree-refit identity and preparation-cost gate."""

import hashlib
import json
import math
import statistics
import sys
EXPECTED_INPUT_SHA256 = "23b6fe726b181e7f5f64297eb8a3c95790f1030644ce1f44d3b70b211999070c"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "_diag/tree_refit_gpu.json"
    with open(path, "rb") as stream:
        raw = stream.read()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != EXPECTED_INPUT_SHA256:
        print(
            "G63: UNEVALUABLE — frozen input missing "
            f"(expected {EXPECTED_INPUT_SHA256}, got {actual_sha256})"
        )
        raise SystemExit(2)
    data = json.loads(raw)

    full = [float(value) for value in data["full_prepare_us"]]
    refit = [float(value) for value in data["refit_prepare_us"]]
    full_median = statistics.median(full)
    refit_median = statistics.median(refit)
    ratio = refit_median / full_median if full_median > 0.0 else math.inf

    identity = (
        data["source_order_identical"]
        and data["node_count_identical"]
        and data["node_ranges_identical"]
        and data["particle_gradient_identical"]
        and data["particle_gradient_finite"]
    )
    passed = identity and math.isfinite(ratio) and ratio <= 0.25

    print("=== G63: persistent tree refit ===")
    print(
        "identity: order=%s node_count=%s ranges=%s gradient=%s finite=%s"
        % (
            data["source_order_identical"],
            data["node_count_identical"],
            data["node_ranges_identical"],
            data["particle_gradient_identical"],
            data["particle_gradient_finite"],
        )
    )
    print(
        "nodes: refit=%d fresh=%d  dispatches: refit=%d fresh=%d"
        % (
            data["refit_node_count"],
            data["full_node_count"],
            data["refit_dispatches"],
            data["full_dispatches"],
        )
    )
    print("fresh prepare us: %s  median=%.1f" % (full, full_median))
    print("refit prepare us: %s  median=%.1f" % (refit, refit_median))
    print("refit/fresh median ratio: %.6f  threshold<=0.25" % ratio)
    print("G63: %s" % ("PASS" if passed else "FAIL"))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
