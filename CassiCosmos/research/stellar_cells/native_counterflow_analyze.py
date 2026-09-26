"""Measure native graph wave-energy counterflow in the retained sphere campaign."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from native_counterflow_currents import NativeCurrentGraph
from native_counterflow_geometry import measure_channels
from native_sphere_analyze import BlobReader, FIELD, file_sha, read_json, require, save_json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SPEC = HERE / "native_counterflow_spec.json"
ANALYSIS_FILES = [SPEC, HERE / "native_counterflow_prereg.md", Path(__file__),
                  HERE / "native_counterflow_currents.py", HERE / "native_counterflow_geometry.py",
                  HERE / "native_counterflow_calibrate.py", HERE / "native_counterflow_verify.py",
                  HERE / "native_sphere_analyze.py"]


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): file_sha(p) for p in ANALYSIS_FILES}


def coefficients(cfg, count):
    volume = float(np.prod(2.0 * np.asarray(cfg["extents"])))
    h = (volume / count) ** (1.0 / 3.0)
    return {"c2": float(np.float32(h * h * cfg["c2_multiplier"])),
            "phi": float(np.float32((1.0 + np.sqrt(5.0)) / 2.0)),
            "omega2": float(np.float32(20.0 * cfg["conversion_multiplier"])),
            "mass_scale": float(np.float32(.001 * volume / count * cfg["mass_source_multiplier"])),
            "spacing": h}


def comparison(actual, reference, atol, rtol):
    delta = np.abs(np.asarray(actual) - np.asarray(reference))
    tolerance = atol + rtol * np.abs(reference)
    return {"comparisons": int(delta.size), "mismatches": int(np.count_nonzero(delta > tolerance)),
            "max_abs_error": float(np.max(delta)), "max_tolerance_ratio": float(np.max(delta / tolerance)),
            "atol": atol, "rtol": rtol}


def radial_cuts(graph, powers_y, powers_i, center, radius, criteria):
    distance = np.linalg.norm(graph.world_sites - center, axis=1)
    result = []
    for ratio in criteria["radii_over_R"]:
        inside = distance <= ratio * radius
        left, right = inside[graph.edge_i], inside[graph.edge_j]
        crossing = left != right
        direction = np.where(left[crossing], 1.0, -1.0)
        yy, ii = powers_y[crossing] * direction, powers_i[crossing] * direction
        yo, yi = float(np.maximum(yy, 0).sum()), float(np.maximum(-yy, 0).sum())
        io, ie = float(np.maximum(ii, 0).sum()), float(np.maximum(-ii, 0).sum())
        ty, ti = yo + yi, io + ie
        nonzero = min(ty, ti) > criteria["flux_floor"]
        by, bi = ((yo - yi) / ty if ty > criteria["flux_floor"] else None,
                  (io - ie) / ti if ti > criteria["flux_floor"] else None)
        balance = 2 * min(ty, ti) / (ty + ti) if ty + ti > criteria["flux_floor"] else None
        count = int(np.count_nonzero(crossing))
        eligible = bool(nonzero and count >= criteria["min_crossing_edges"])
        strong = bool(eligible and by * bi < 0 and min(abs(by), abs(bi)) >= criteria["bias_abs_min"]
                      and balance >= criteria["throughput_balance_min"])
        association = (yo * ie - yi * io) / (ty * ti) if nonzero else None
        result.append({"radius_over_R": ratio, "crossing_edges": count,
                       "Y_out": yo, "Y_in": yi, "I_out": io, "I_in": ie,
                       "Y_net_out": yo - yi, "I_net_out": io - ie,
                       "bias_y": by, "bias_i": bi, "throughput_balance": balance,
                       "species_direction_association": association,
                       "nonzero_components": bool(nonzero), "eligible": eligible, "strong_opposition": strong})
    return result


def local_diagnostics(graph, values, center, radius, floor):
    result = {}
    r = np.linalg.norm(graph.world_sites - center, axis=1)
    py, pi = values["edge_power_y"], values["edge_power_i"]
    jy, ji = values["current_y"], values["current_i"]
    ny, ni = np.linalg.norm(jy, axis=1), np.linalg.norm(ji, axis=1)
    for name, fraction in (("core", .5), ("cloud", 1.0)):
        mask = r <= radius * fraction
        edges = mask[graph.edge_i] & mask[graph.edge_j]
        denominator = float(np.sum(np.abs(py[edges]) + np.abs(pi[edges])))
        cancel = float(np.sum(np.abs(py[edges]) + np.abs(pi[edges]) - np.abs(py[edges] + pi[edges])))
        eligible = mask & (ny > floor) & (ni > floor)
        weight = graph.volumes[eligible] * np.minimum(ny[eligible], ni[eligible])
        dots = np.sum(jy[eligible] * ji[eligible], axis=1) / (ny[eligible] * ni[eligible])
        result[name] = {"sites": int(mask.sum()), "interior_edges": int(edges.sum()),
                        "nonzero_power_edges": int(np.count_nonzero(edges & ((np.abs(py) + np.abs(pi)) > floor))),
                        "power_denominator": denominator,
                        "same_edge_cancellation": cancel / denominator if denominator > floor else None,
                        "alignment_comparisons": int(eligible.sum()),
                        "current_alignment": float(np.average(dots, weights=weight)) if weight.sum() > floor else None,
                        "Y_current_intensity": float(np.sum(graph.volumes[mask] * ny[mask])),
                        "I_current_intensity": float(np.sum(graph.volumes[mask] * ni[mask]))}
    return result


def window_summary(frames, spec):
    chosen = {}
    for frame in frames:
        chosen[frame["step"]] = frame
    final = [f for f in chosen.values() if spec["windows"]["primary"][0] - 1e-9 <= f["t"] <= spec["windows"]["primary"][1] + 1e-9]
    require(bool(final), "empty primary window")
    cut_index = spec["radial"]["radii_over_R"].index(spec["radial"]["primary_radius_over_R"])
    radial = [f["radial"][cut_index] for f in final]
    geometry = [f["geometry"] for f in final]
    rp = np.array([r["strong_opposition"] for r in radial])
    hp = np.array([g["detected"] for g in geometry])
    detected = [g for g in geometry if g["detected"]]
    signs = [np.sign(g["winding"]["winding_signed_turns"]) for g in detected]
    handedness = max(signs.count(1), signs.count(-1)) / len(signs) if signs else None
    axis_dots = [abs(float(np.dot(a["axis"], b["axis"]))) for a, b in zip(detected, detected[1:])]
    twist_changes = [abs(a["winding"]["winding_signed_turns"] - b["winding"]["winding_signed_turns"]) for a, b in zip(detected, detected[1:])]
    even_odd = {}
    for name, values in (("radial_persistence_fraction", rp), ("helix_persistence_fraction", hp)):
        means = [float(values[offset::2].mean()) if values[offset::2].size else None for offset in (0, 1)]
        difference = abs(means[0] - means[1]) if None not in means else None
        even_odd[name] = {"even_count": int(values[::2].size), "odd_count": int(values[1::2].size),
                          "even_fraction": means[0], "odd_fraction": means[1], "difference": difference,
                          "passed": difference is not None and difference <= spec["verification"]["temporal_subsample_metric_tolerance"]}
    temporal = bool(detected and len(axis_dots) > 0
                    and min(axis_dots) >= spec["geometry"]["axis_adjacent_cosine_abs_min"]
                    and max(twist_changes) <= spec["geometry"]["temporal_winding_change_max"])
    radial_persistent = float(rp.mean()) >= spec["radial"]["persistence_fraction_min"]
    helical_persistent = bool(float(hp.mean()) >= spec["geometry"]["persistence_fraction_min"]
                             and handedness is not None and handedness >= spec["geometry"]["handedness_consistency_min"] and temporal)
    separation = [s["separation_over_spacing"] for g in geometry for s in g["slices"] if s.get("separation_over_spacing") is not None]
    bias_summary = {}
    for name in ("bias_y", "bias_i", "throughput_balance"):
        values = [r[name] for r in radial if r[name] is not None]
        bias_summary[name] = {"attempts": len(values), "min": min(values) if values else None,
                              "median": float(np.median(values)) if values else None, "max": max(values) if values else None}
    return {"samples": len(final), "time_bounds": [final[0]["t"], final[-1]["t"]],
            "radial_eligible_samples": sum(r["eligible"] for r in radial),
            "radial_opposed_samples": int(rp.sum()), "radial_persistence_fraction": float(rp.mean()),
            "radial_persistent": radial_persistent, "radial_metrics": bias_summary,
            "helix_detected_samples": int(hp.sum()), "helix_persistence_fraction": float(hp.mean()),
            "helical_persistent": helical_persistent,
            "axis_identifiable_samples": sum(g["axis_identifiable"] for g in geometry),
            "resolved_slice_count_max": max(g["resolved_slice_count"] for g in geometry),
            "consecutive_resolved_max": max(g["consecutive_resolved_count"] for g in geometry),
            "separation_over_spacing_max": max(separation) if separation else None,
            "handedness_consistency": handedness, "adjacent_detected_axis_comparisons": len(axis_dots),
            "minimum_adjacent_axis_cosine": min(axis_dots) if axis_dots else None,
            "maximum_adjacent_twist_change": max(twist_changes) if twist_changes else None,
            "detected_temporal_consistency": temporal,
            "geometry_failure_counts": dict(Counter(reason for g in geometry for reason in g["reasons"])),
            "even_odd": even_odd}


def analyze_arm(source, output, cfg, parent_arm, run, manifest, spec):
    directory = source / cfg["id"]
    receipt_path = directory / "receipt.json"
    require(file_sha(receipt_path) == parent_arm["receipt_sha256"], "parent-bound receipt changed")
    receipt = read_json(receipt_path)
    require(receipt["config"] == cfg and receipt["status"] == "COMPLETE" and not receipt["errors"], "invalid native arm")
    require(receipt["source_hashes"] == {**manifest["source_hashes"], "engine_variant": run["variant"]["variant_sha256"]}, "arm source identity")
    count = int(receipt["runtime_configuration"]["site_count"])
    coeff = coefficients(cfg, count)
    reader = BlobReader(directory, int(cfg["particle_count"]), count, cfg["freeze_field"])
    snapshots = receipt["snapshots"]
    first = snapshots[0]["files"]
    geometry = {key: reader.load(key, first[key]) for key in ("sites", "site_vol", "offsets", "neighbors")}
    graph = NativeCurrentGraph(geometry["sites"], geometry["site_vol"], geometry["offsets"], geometry["neighbors"],
                               cfg["extents"], coeff["c2"], coeff["phi"], spec["current_definition"]["volume_floor"])
    frames, endpoint_checks = [], []
    balance_comparisons = balance_mismatches = 0
    maximum_balance_ratio = 0.0
    frozen_zero = True
    raw_bindings = {}
    final_values = None
    for snapshot in snapshots:
        files = snapshot["files"]
        for role in ("sites", "site_vol"):
            require(files[role]["raw_sha256"] == first[role]["raw_sha256"], "moving native geometry")
        for role in ("offsets", "neighbors"):
            if role in files:
                require(files[role]["raw_sha256"] == first[role]["raw_sha256"], "changed fixed native graph")
        # Read every declared array so hash/shape validation covers all retained observations.
        arrays = {role: reader.load(role, item) for role, item in files.items()}
        raw_bindings.update({item["path"]: {k: item[k] for k in ("sha256", "raw_sha256", "bytes", "raw_bytes")}
                             for item in files.values()})
        values = graph.evaluate(*(arrays[role] for role in FIELD), coeff["omega2"], coeff["mass_scale"], arrays["site_mass"])
        pos = arrays["pos"].astype(np.float64)
        center = np.average(pos[:, :3], axis=0, weights=pos[:, 3])
        atol, rtol = spec["verification"]["semidiscrete_balance_atol"], spec["verification"]["semidiscrete_balance_rtol"]
        residual = np.abs(values["balance_residual"])
        tolerance = atol + rtol * values["balance_scale"]
        bad = int(np.count_nonzero(residual > tolerance))
        balance_comparisons += count
        balance_mismatches += bad
        maximum_balance_ratio = max(maximum_balance_ratio, float(np.max(residual / tolerance)))
        radial = radial_cuts(graph, values["edge_power_y"], values["edge_power_i"], center, cfg["radius"], spec["radial"])
        channels = measure_channels(graph.world_sites, values["current_y"], values["current_i"], graph.volumes,
                                    center, cfg["radius"], coeff["spacing"], spec["geometry"])
        frozen_zero &= bool(np.all(values["edge_power_y"] == 0) and np.all(values["edge_power_i"] == 0))
        frames.append({"step": snapshot["step"], "phase": snapshot["phase"], "t": snapshot["step"] * cfg["dt"],
                       "center": center, "radial": radial, "geometry": channels,
                       "local": local_diagnostics(graph, values, center, cfg["radius"], spec["radial"]["flux_floor"]),
                       "energy": {"graph_energy": float(np.sum(values["energy_by_site"])),
                                  "source_work_rate": float(np.sum(values["source_power_by_site"])),
                                  "semidiscrete_energy_derivative": float(np.sum(values["energy_derivative_by_site"])),
                                  "balance_comparisons": count, "balance_mismatches": bad,
                                  "max_balance_abs": float(residual.max()), "max_balance_tolerance_ratio": float(np.max(residual / tolerance))}})
        if "grad_y" in arrays:
            check = {"step": snapshot["step"], "t": snapshot["step"] * cfg["dt"], "channels": {}}
            for role in ("grad_y", "grad_i", "lap_y", "lap_i"):
                prefix = "gradient" if role.startswith("grad") else "lap"
                reference = arrays[role][:, :3] if prefix == "gradient" else arrays[role]
                check["channels"][role] = comparison(values[role], reference, spec["verification"][prefix + "_atol"], spec["verification"][prefix + "_rtol"])
            endpoint_checks.append(check)
        final_values = values
    require(len(endpoint_checks) == 2, "both native derivative endpoints required")
    final = window_summary(frames, spec)
    final["axial_slice_width_over_spacing"] = (2 * cfg["radius"] / spec["geometry"]["slices"]) / coeff["spacing"]
    final["helical_spatial_resolution_eligible"] = final["axial_slice_width_over_spacing"] >= spec["geometry"]["slice_width_over_spacing_min"]
    endpoint_mismatches = sum(c["mismatches"] for e in endpoint_checks for c in e["channels"].values())
    valid = balance_mismatches == 0 and endpoint_mismatches == 0 and (not cfg["freeze_field"] or frozen_zero)
    radial_quality = valid and final["even_odd"]["radial_persistence_fraction"]["passed"]
    helix_quality = valid and final["helical_spatial_resolution_eligible"] and final["even_odd"]["helix_persistence_fraction"]["passed"]
    all_detected = sum(f["geometry"]["detected"] for f in frames)
    summary = {"id": cfg["id"], "config": cfg, "coefficients": coeff, "source_receipt_sha256": file_sha(receipt_path),
               "snapshots": len(frames), "status": "VALID" if valid else "INVALID", "topology": graph.topology_summary,
               "integrity": {"raw_blob_count": len(raw_bindings), "raw_declarations": reader.declarations,
                             "decoded_elements": reader.decoded_elements, "balance_comparisons": balance_comparisons,
                             "balance_mismatches": balance_mismatches, "max_balance_tolerance_ratio": maximum_balance_ratio,
                             "endpoint_mismatches": endpoint_mismatches, "endpoint_checks": endpoint_checks,
                             "all_bond_currents_exactly_zero": frozen_zero},
               "final_window": final, "all_time_helix_detected_samples": all_detected,
               "radial_verdict": ("CANDIDATE_REQUIRES_DENSE_CONFIRMATION" if final["radial_persistent"] else "CONTRADICTS") if radial_quality else "INCONCLUSIVE",
               "helical_verdict": ("CANDIDATE_REQUIRES_DENSE_CONFIRMATION" if final["helical_persistent"] else "DOES NOT EMERGE") if helix_quality else "INCONCLUSIVE",
               "material_verdict": "INCONCLUSIVE: no native material/species current map"}
    arm_output = output / cfg["id"]
    arm_output.mkdir(exist_ok=True)
    save_json(arm_output / "frames.json", {"schema": "native_counterflow_frames_v1", "frames": frames})
    save_json(arm_output / "raw_bindings.json", raw_bindings)
    np.savez_compressed(arm_output / "final_current_witness.npz", edge_i=graph.edge_i, edge_j=graph.edge_j,
                        **{k: final_values[k] for k in ("edge_power_y", "edge_power_i", "current_y", "current_i",
                                                      "energy_derivative_by_site", "divergence_by_site", "source_power_by_site")})
    summary["artifacts"] = {name: file_sha(arm_output / name) for name in ("frames.json", "raw_bindings.json", "final_current_witness.npz")}
    save_json(arm_output / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = read_json(SPEC)
    source = ROOT / spec["source_campaign"]
    output = args.output.resolve() if args.output else ROOT / spec["output"]
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "analysis.json").exists(), "completed analysis already exists; preserve it")
    hashes = source_hashes()
    calibration = read_json(output / "calibration.json")
    require(calibration["status"] == "PASS" and calibration["source_hashes"] == hashes, "calibration absent, failed or stale")
    require(file_sha(source / "campaign.json") == spec["source_campaign_sha256"], "parent manifest changed")
    require(file_sha(source / "analysis.json") == spec["source_analysis_sha256"], "parent analysis changed")
    manifest, parent = read_json(source / "campaign.json"), read_json(source / "analysis.json")
    require(parent["status"] == "VALID", "parent experiment not valid")
    native_paths = ("scripts/cassi_physics_engine.gd", "compute/cassi_site_physics.glsl",
                    ".godot/imported/cassi_site_physics.glsl-44a11b5a4a9a4135b63a4a09dad31cb4.res")
    native_hashes = {p: file_sha(ROOT / p) for p in native_paths}
    require(all(native_hashes[p] == manifest["source_hashes"][p] for p in native_paths), "current operator differs from recorded operator")
    planned = {a["id"]: {**manifest["spec"]["defaults"], **a} for a in manifest["spec"]["arms"]}
    runs = {r["id"]: r for r in manifest["runs"]}
    require(set(planned) == set(spec["arm_ids"]), "registered arm coverage changed")
    arms = {}
    for name in spec["arm_ids"]:
        print("MEASURE " + name, flush=True)
        arms[name] = analyze_arm(source, output, planned[name], parent["arms"][name], runs[name], manifest, spec)
        f = arms[name]["final_window"]
        print(f"  {arms[name]['status']} radial={f['radial_opposed_samples']}/{f['samples']} helix={f['helix_detected_samples']}/{f['samples']} resolved_max={f['consecutive_resolved_max']}", flush=True)
    triggered = [name for name in spec["primary_arm_ids"] if arms[name]["final_window"]["radial_persistent"] or arms[name]["all_time_helix_detected_samples"]]
    result = {"schema": "native_counterflow_analysis_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "VALID" if all(a["status"] == "VALID" for a in arms.values()) else "INVALID",
              "source_campaign": spec["source_campaign"], "source_campaign_sha256": file_sha(source / "campaign.json"),
              "source_analysis_sha256": file_sha(source / "analysis.json"), "source_hashes": hashes,
              "native_operator_hashes": native_hashes, "calibration_sha256": file_sha(output / "calibration.json"),
              "arm_count": len(arms), "snapshot_count": sum(a["snapshots"] for a in arms.values()),
              "primary_arm_ids": spec["primary_arm_ids"], "dense_triggered_arm_ids": triggered,
              "dense_confirmation_required": bool(triggered), "arms": arms,
              "scope": "Native graph wave-energy currents, saved times 0..32; no material/species velocity inference, no exhaustive knotted or toroidal geometry claim."}
    save_json(output / "analysis.json", result)
    print(f"{result['status']}: {result['arm_count']} arms, {result['snapshot_count']} snapshots; dense trigger={triggered}", flush=True)
    return 0 if result["status"] == "VALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
