"""Calibrate the frozen detector before classifying retained native observations."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from native_counterflow_analyze import ROOT, SPEC, comparison, radial_cuts, source_hashes
from native_counterflow_currents import NativeCurrentGraph
from native_counterflow_geometry import measure_channels
from native_sphere_analyze import file_sha, read_json, save_json


def regular_graph(n=12):
    indices = np.indices((n, n, n)).reshape(3, -1).T
    sites = indices.astype(float) + .5
    rows = []
    for axis in range(3):
        for sign in (-1, 1):
            neighbor = indices.copy()
            neighbor[:, axis] = (neighbor[:, axis] + sign) % n
            rows.append(np.ravel_multi_index(neighbor.T, (n, n, n)))
    neighbors = np.column_stack(rows).reshape(-1).astype(np.uint32)
    offsets = np.arange(0, 6 * n**3 + 1, 6, dtype=np.uint32)
    return NativeCurrentGraph(sites, np.ones(n**3), offsets, neighbors, np.full(3, n / 2), 1.0,
                              float(np.float32((1 + np.sqrt(5)) / 2)))


def current_calibration(spec):
    graph = regular_graph()
    x = graph.world_sites[:, 0]
    k = 2 * np.pi / 12
    omega = np.sqrt(2 * (1 - np.cos(k)))
    field, momentum = np.cos(k * x), omega * np.sin(k * x)
    zeros = np.zeros(x.size)
    measured = graph.evaluate(field, zeros, momentum, zeros, 0.0, 0.0, zeros)
    dx = graph.displacement[:, 0]
    midpoint = x[graph.edge_i] + .5 * dx
    analytic = omega * np.sin(k * midpoint)**2 * np.sin(k * dx) / graph.distance
    gradient = np.zeros((x.size, 3))
    gradient[:, 0] = -2 * np.sin(k * x) * np.sin(k) / (2 + float(np.float32(1e-6)))
    lap = 2 * (np.cos(k) - 1) * field
    checks = {"traveling_wave_bond_power": comparison(measured["edge_power_y"], analytic, 1e-10, 1e-10),
              "traveling_wave_discrete_gradient": comparison(measured["grad_y"], gradient, 1e-10, 1e-10),
              "traveling_wave_discrete_laplacian": comparison(measured["lap_y"], lap, 1e-10, 1e-10),
              "traveling_wave_pointwise_balance": comparison(measured["balance_residual"], zeros, 1e-9, 1e-9)}
    r2 = np.sum(graph.world_sites**2, axis=1)
    pulse = np.exp(-r2 / 18)
    opposed = graph.evaluate(pulse, pulse, pulse, -pulse / graph.phi, 20.0, .001, np.ones(x.size))
    cuts = radial_cuts(graph, opposed["edge_power_y"], opposed["edge_power_i"], np.zeros(3), 5.0, spec["radial"])
    checks["radial_opposed_bond_identity"] = comparison(opposed["edge_power_y"], -opposed["edge_power_i"], 1e-10, 1e-10)
    checks["radial_pointwise_balance"] = comparison(opposed["balance_residual"], zeros, 1e-9, 1e-9)
    # The innermost cut has only 24 edges: the frozen 32-edge guard must reject it.
    expected_cut_detection = [False, True, True, True]
    cut_checks = [c["strong_opposition"] == expected for c, expected in zip(cuts, expected_cut_detection)]
    passed = all(c["comparisons"] > 0 and c["mismatches"] == 0 for c in checks.values()) and all(cut_checks)
    return {"status": "PASS" if passed else "FAIL", "checks": checks, "radial_counterwave_cuts": cuts,
            "expected_radial_detection": expected_cut_detection, "radial_detection_checks": cut_checks,
            "meaning": "Analytic measurement inputs; not native spontaneous-formation evidence."}


def geometry_inputs(name, calibration):
    h, radius = calibration["geometry_spacing"], calibration["geometry_radius"]
    coordinate = np.arange(-radius, radius + h / 2, h)
    sites = np.stack(np.meshgrid(coordinate, coordinate, coordinate, indexing="ij"), axis=-1).reshape(-1, 3)
    a, k, sigma = calibration["helix_radius"], calibration["helix_k"], calibration["transverse_sigma"]
    if name == "straight_counterflow":
        k = 0.0
    if name == "coincident_channels":
        a = 0.0
    angle = k * sites[:, 2]
    centers = np.column_stack((a * np.cos(angle), a * np.sin(angle)))
    def channel(sign):
        distance2 = np.sum((sites[:, :2] - sign * centers)**2, axis=1)
        intensity = np.exp(-distance2 / (2 * sigma**2))
        tangent = np.column_stack((-sign * a * k * np.sin(angle), sign * a * k * np.cos(angle), np.ones(angle.size)))
        tangent /= np.linalg.norm(tangent, axis=1)[:, None]
        return intensity[:, None] * tangent
    jy, ji = channel(1), -channel(-1)
    if name == "helical_coflow":
        ji *= -1
    elif name == "radial_flow":
        jy = sites * np.exp(-np.sum(sites**2, axis=1) / 50)[:, None]
        ji = -jy
    elif name == "zero_current":
        jy = np.zeros_like(sites)
        ji = np.zeros_like(sites)
    elif name == "rotated_helical_counterflow":
        axis = np.array([1., 2., 3.]) / np.sqrt(14)
        cross = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        rotation = np.eye(3) + np.sin(.71) * cross + (1 - np.cos(.71)) * cross @ cross
        sites, jy, ji = sites @ rotation.T, jy @ rotation.T, ji @ rotation.T
    return sites, jy, ji, np.full(sites.shape[0], h**3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = read_json(SPEC)
    output = args.output or ROOT / spec["output"]
    output.mkdir(parents=True, exist_ok=True)
    current = current_calibration(spec)
    geometry = {}
    positive = {"helical_counterflow", "rotated_helical_counterflow"}
    for name in spec["calibration"]["cases"]:
        sites, jy, ji, volumes = geometry_inputs(name, spec["calibration"])
        result = measure_channels(sites, jy, ji, volumes, np.zeros(3), spec["calibration"]["geometry_radius"],
                                  spec["calibration"]["geometry_spacing"], spec["geometry"])
        passed = bool(result["detected"] == (name in positive))
        geometry[name] = {"expected_detected": name in positive, "passed": passed, "measurement": result}
        if name == "helical_counterflow":
            np.savez_compressed(output / "analytic_helix_input.npz", sites=sites, current_y=jy, current_i=ji, volumes=volumes)
        print(f"CALIBRATE {name}: expected={name in positive} detected={result['detected']} resolved={result['consecutive_resolved_count']} winding={result['winding_turns']} reasons={result['reasons']}", flush=True)
    status = "PASS" if current["status"] == "PASS" and all(g["passed"] for g in geometry.values()) else "FAIL"
    receipt = {"schema": "native_counterflow_calibration_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
               "status": status, "source_hashes": source_hashes(), "current": current, "geometry": geometry,
               "analytic_helix_input_sha256": file_sha(output / "analytic_helix_input.npz"),
               "meaning": "Detector sensitivity and specificity on declared analytic inputs, not native PDE emergence."}
    save_json(output / "calibration.json", receipt)
    print(f"CALIBRATION {status}; current={current['status']}", flush=True)
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
