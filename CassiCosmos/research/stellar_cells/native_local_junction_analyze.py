"""Measure localized paired Yang/Yin graph-current junctions in retained states."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from native_counterflow_analyze import coefficients
from native_counterflow_currents import NativeCurrentGraph
from native_sphere_analyze import BlobReader, FIELD, file_sha, read_json, require, save_json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "native_local_junction_spec.json"
SOURCE_FILES = [SPEC_PATH, HERE / "native_local_junction_prereg.md", Path(__file__),
                HERE / "native_local_junction_verify.py", HERE / "native_counterflow_currents.py",
                HERE / "native_sphere_analyze.py"]


def hashes():
    return {p.relative_to(ROOT).as_posix(): file_sha(p) for p in SOURCE_FILES}


def scalar(value):
    return None if value is None else float(value)


def vector(value):
    return None if value is None else [float(x) for x in value]


def canonical_axis(axis):
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    pivot = int(np.argmax(np.abs(axis)))
    return -axis if axis[pivot] < 0 else axis


def channel_stats(points, current, weights, selected):
    selected = np.asarray(selected, dtype=int)
    if selected.size == 0:
        return None
    weight = weights[selected]
    total, square = float(weight.sum()), float(np.sum(weight**2))
    if total <= 0 or square <= 0:
        return None
    centroid = np.average(points[selected], axis=0, weights=weight)
    centered = points[selected] - centroid
    covariance = (centered * weight[:, None]).T @ centered / total
    eigenvalues, eigenvectors = np.linalg.eigh((covariance + covariance.T) / 2)
    axis = canonical_axis(eigenvectors[:, -1])
    mean_current = np.average(current[selected], axis=0, weights=weight)
    mean_norm = float(np.linalg.norm(mean_current))
    mean_speed = float(np.average(np.linalg.norm(current[selected], axis=1), weights=weight))
    return {"site_count": int(selected.size), "weight_sum": total, "effective_n": total**2 / square,
            "centroid": centroid, "covariance_eigenvalues": eigenvalues, "axis": axis,
            "linearity_ratio": float(eigenvalues[-1] / max(eigenvalues[-2], 1e-30)),
            "mean_current": mean_current, "coherence": mean_norm / mean_speed if mean_speed > 0 else None,
            "axis_alignment": abs(float(np.dot(mean_current / mean_norm, axis))) if mean_norm > 0 else None}


def closest_lines(pa, a, pb, b):
    dot = float(np.dot(a, b))
    denominator = 1 - dot**2
    if denominator <= 1e-12:
        return None, None, None
    w = pa - pb
    aw, bw = float(np.dot(a, w)), float(np.dot(b, w))
    s = (dot * bw - aw) / denominator
    t = (bw - dot * aw) / denominator
    left, right = pa + s * a, pb + t * b
    return float(np.linalg.norm(left - right)), float(s), float(t)


def measure_frame(points, current_y, current_i, volumes, center, radius, spacing, criteria):
    points = np.asarray(points, dtype=float)
    currents = (np.asarray(current_y, dtype=float), np.asarray(current_i, dtype=float))
    volumes = np.asarray(volumes, dtype=float)
    inside = np.linalg.norm(points - center, axis=1) <= radius * criteria["sphere_radius_over_R"]
    norms = [np.linalg.norm(current, axis=1) for current in currents]
    weights = [volumes * norm for norm in norms]
    maxima = [float(weight[inside].max()) if inside.any() else 0.0 for weight in weights]
    if min(maxima) <= 0:
        return {"candidate_pool": 0, "ranked_centers": 0, "evaluated_centers": 0, "qualifying_count": 0,
                "component_weight_max": maxima, "candidates": []}
    joint = np.sqrt((weights[0] / maxima[0]) * (weights[1] / maxima[1]))
    pool = np.flatnonzero(inside & (joint >= criteria["joint_score_min"]))
    order = pool[np.lexsort((pool, -joint[pool]))]
    retained = []
    suppression = criteria["nonmaximum_suppression_radius_over_h"] * spacing
    for site in order:
        if len(retained) >= criteria["max_ranked_centers"]:
            break
        if all(np.linalg.norm(points[site] - points[prior]) > suppression for prior in retained):
            retained.append(int(site))
    tree = cKDTree(points)
    candidates = []
    for site in retained:
        neighbors = np.asarray(tree.query_ball_point(points[site], criteria["neighborhood_radius_over_h"] * spacing), dtype=int)
        stats = [channel_stats(points, currents[k], weights[k], neighbors) for k in range(2)]
        reasons = []
        if neighbors.size < criteria["minimum_sites"]:
            reasons.append("insufficient neighborhood sites")
        for label, data in zip(("Y", "I"), stats):
            if data is None:
                reasons.append(label + " channel unavailable")
                continue
            if data["effective_n"] < criteria["effective_sites_min"]:
                reasons.append(label + " effective support below threshold")
            if data["linearity_ratio"] < criteria["linearity_ratio_min"]:
                reasons.append(label + " channel is not line-like")
            if data["coherence"] is None or data["coherence"] < criteria["current_coherence_min"]:
                reasons.append(label + " current coherence below threshold")
            if data["axis_alignment"] is None or data["axis_alignment"] < criteria["current_axis_alignment_min"]:
                reasons.append(label + " current is not aligned with fitted channel")
        angle = distance = parameter_y = parameter_i = centroid_distance = current_dot = None
        if all(data is not None for data in stats):
            cosine = abs(float(np.dot(stats[0]["axis"], stats[1]["axis"])))
            angle = float(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
            distance, parameter_y, parameter_i = closest_lines(stats[0]["centroid"], stats[0]["axis"], stats[1]["centroid"], stats[1]["axis"])
            centroid_distance = float(np.linalg.norm(stats[0]["centroid"] - stats[1]["centroid"]))
            uy = stats[0]["mean_current"] / np.linalg.norm(stats[0]["mean_current"])
            ui = stats[1]["mean_current"] / np.linalg.norm(stats[1]["mean_current"])
            current_dot = float(np.dot(uy, ui))
            if angle < criteria["crossing_angle_min_degrees"]:
                reasons.append("component lines are too parallel for an intersection")
            if distance is None or distance > criteria["line_closest_approach_max_over_h"] * spacing:
                reasons.append("fitted lines do not approach closely enough")
            if parameter_y is None or max(abs(parameter_y), abs(parameter_i)) > criteria["closest_parameter_abs_max_over_h"] * spacing:
                reasons.append("closest approach lies outside local fitted segments")
            if centroid_distance > criteria["centroid_distance_max_over_h"] * spacing:
                reasons.append("component centroids are too far apart")
        qualifying = len(reasons) == 0
        encoded_stats = []
        for data in stats:
            encoded_stats.append(None if data is None else {key: vector(value) if key in ("centroid", "axis", "mean_current") else ([float(x) for x in value] if key == "covariance_eigenvalues" else scalar(value)) for key, value in data.items()})
        candidates.append({"center_site": site, "center": vector(points[site]), "joint_score": float(joint[site]),
                           "neighborhood_site_count": int(neighbors.size), "Y": encoded_stats[0], "I": encoded_stats[1],
                           "crossing_angle_degrees": angle, "line_closest_approach": distance,
                           "line_closest_approach_over_h": None if distance is None else distance / spacing,
                           "closest_parameter_y_over_h": None if parameter_y is None else parameter_y / spacing,
                           "closest_parameter_i_over_h": None if parameter_i is None else parameter_i / spacing,
                           "centroid_distance_over_h": None if centroid_distance is None else centroid_distance / spacing,
                           "mean_current_dot": current_dot, "qualifying": qualifying, "reasons": reasons})
    return {"candidate_pool": int(pool.size), "ranked_centers": min(int(order.size), criteria["max_ranked_centers"]),
            "evaluated_centers": len(candidates), "qualifying_count": sum(c["qualifying"] for c in candidates),
            "component_weight_max": maxima, "candidates": candidates}


def match_tracks(frames, spacing, criteria):
    active, completed = [], []
    for frame_index, frame in enumerate(frames):
        candidates = [c for c in frame["junctions"]["candidates"] if c["qualifying"]]
        available = set(range(len(candidates)))
        next_active = []
        for track in active:
            matches = []
            previous = track["members"][-1]
            for index in available:
                candidate = candidates[index]
                distance = np.linalg.norm(np.asarray(previous["center"]) - candidate["center"])
                axes = [abs(float(np.dot(previous[k]["axis"], candidate[k]["axis"]))) for k in ("Y", "I")]
                if distance <= criteria["match_center_distance_max_over_h"] * spacing and min(axes) >= criteria["axis_cosine_abs_min"]:
                    matches.append((distance, candidate["center_site"], index))
            if matches:
                _, _, index = min(matches)
                available.remove(index)
                candidate = candidates[index]
                next_active.append({"start_frame": track["start_frame"], "members": track["members"] + [candidate]})
            else:
                completed.append(track)
        for index in sorted(available, key=lambda k: candidates[k]["center_site"]):
            next_active.append({"start_frame": frame_index, "members": [candidates[index]]})
        active = next_active
    completed.extend(active)
    encoded = [{"start_frame": t["start_frame"], "length": len(t["members"]),
                "center_sites": [m["center_site"] for m in t["members"]], "centers": [m["center"] for m in t["members"]]}
               for t in completed]
    encoded.sort(key=lambda t: (-t["length"], t["start_frame"], t["center_sites"]))
    maximum = encoded[0]["length"] if encoded else 0
    return {"track_count": len(encoded), "maximum_consecutive_length": maximum,
            "persistent": maximum >= criteria["minimum_consecutive_saved_frames"], "tracks": encoded}


def calibration_case(name, spec):
    h, radius = spec["calibration"]["spacing"], spec["calibration"]["radius"]
    coordinate = np.arange(-radius, radius + h / 2, h)
    points = np.stack(np.meshgrid(coordinate, coordinate, coordinate, indexing="ij"), axis=-1).reshape(-1, 3)
    sigma = spec["calibration"]["tube_sigma_over_h"] * h
    wy = np.exp(-(points[:, 1]**2 + points[:, 2]**2) / (2 * sigma**2))
    wi = np.exp(-(points[:, 0]**2 + points[:, 2]**2) / (2 * sigma**2))
    jy, ji = wy[:, None] * np.array([1., 0, 0]), wi[:, None] * np.array([0., 1, 0])
    if name == "rotated_orthogonal_crossing":
        axis = np.array([1., 2., 3.]) / np.sqrt(14)
        cross = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        rotation = np.eye(3) + np.sin(.67) * cross + (1 - np.cos(.67)) * cross @ cross
        points, jy, ji = points @ rotation.T, jy @ rotation.T, ji @ rotation.T
    elif name == "parallel_separated":
        wy = np.exp(-((points[:, 1] + h)**2 + points[:, 2]**2) / (2 * sigma**2))
        wi = np.exp(-((points[:, 1] - h)**2 + points[:, 2]**2) / (2 * sigma**2))
        jy, ji = wy[:, None] * np.array([1., 0, 0]), wi[:, None] * np.array([-1., 0, 0])
    elif name == "single_component":
        ji[:] = 0
    elif name == "isotropic_radial":
        norm = np.linalg.norm(points, axis=1)
        unit = np.divide(points, norm[:, None], out=np.zeros_like(points), where=norm[:, None] > 0)
        envelope = np.exp(-norm**2 / 2)
        jy, ji = envelope[:, None] * unit, -envelope[:, None] * unit
    elif name == "zero_current":
        jy[:], ji[:] = 0, 0
    return measure_frame(points, jy, ji, np.full(points.shape[0], h**3), np.zeros(3), radius, h, spec["candidate"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = read_json(SPEC_PATH)
    output = args.output or ROOT / spec["output"]
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "analysis.json").exists(), "completed analysis already exists")
    calibration = {}
    for name, expected in spec["calibration"]["cases"].items():
        result = calibration_case(name, spec)
        detected = result["qualifying_count"] > 0
        calibration[name] = {"expected": expected, "detected": detected, "passed": detected == expected, "measurement": result}
        print(f"CALIBRATE {name}: expected={expected} detected={detected} candidates={result['qualifying_count']}", flush=True)
    require(all(c["passed"] for c in calibration.values()), "local detector calibration failed")
    campaign = read_json(ROOT / spec["source_campaign"] / "campaign.json")
    require(file_sha(ROOT / spec["source_campaign"] / "campaign.json") == spec["source_campaign_sha256"], "campaign changed")
    require(file_sha(ROOT / spec["source_counterflow_analysis"]) == spec["source_counterflow_analysis_sha256"], "counterflow analysis changed")
    configs = {a["id"]: {**campaign["spec"]["defaults"], **a} for a in campaign["spec"]["arms"]}
    arms = {}
    for arm_id in spec["arm_ids"]:
        cfg = configs[arm_id]
        receipt = read_json(ROOT / spec["source_campaign"] / arm_id / "receipt.json")
        count = int(receipt["runtime_configuration"]["site_count"])
        coeff = coefficients(cfg, count)
        reader = BlobReader(ROOT / spec["source_campaign"] / arm_id, int(cfg["particle_count"]), count, False)
        first = receipt["snapshots"][0]["files"]
        arrays = {role: reader.load(role, first[role]) for role in ("sites", "site_vol", "offsets", "neighbors")}
        graph = NativeCurrentGraph(arrays["sites"], arrays["site_vol"], arrays["offsets"], arrays["neighbors"], cfg["extents"], coeff["c2"], coeff["phi"])
        frames = []
        for snapshot in receipt["snapshots"]:
            t = snapshot["step"] * cfg["dt"]
            if not (spec["window"][0] - 1e-9 <= t <= spec["window"][1] + 1e-9):
                continue
            files = snapshot["files"]
            state = {role: reader.load(role, files[role]) for role in (*FIELD, "site_mass", "pos")}
            current = graph.evaluate(*(state[role] for role in FIELD), coeff["omega2"], coeff["mass_scale"], state["site_mass"])
            center = np.average(state["pos"][:, :3], axis=0, weights=state["pos"][:, 3])
            measured = measure_frame(graph.world_sites, current["current_y"], current["current_i"], graph.volumes, center, cfg["radius"], coeff["spacing"], spec["candidate"])
            frames.append({"step": snapshot["step"], "t": t, "center": vector(center), "junctions": measured})
        tracks = match_tracks(frames, coeff["spacing"], spec["persistence"])
        qualifying = sum(f["junctions"]["qualifying_count"] for f in frames)
        evaluated = sum(f["junctions"]["evaluated_centers"] for f in frames)
        near = sorted((c for f in frames for c in f["junctions"]["candidates"]), key=lambda c: (len(c["reasons"]), c["line_closest_approach_over_h"] if c["line_closest_approach_over_h"] is not None else 1e99, -c["joint_score"]))[:10]
        parent_quality = read_json(ROOT / spec["source_counterflow_analysis"])["arms"][arm_id]["status"]
        verdict = "CANDIDATE_REQUIRES_NUMERICAL_CONFIRMATION" if tracks["persistent"] else ("DOES NOT EMERGE" if parent_quality == "VALID" else "INCONCLUSIVE")
        arms[arm_id] = {"id": arm_id, "config": cfg, "coefficients": coeff, "frames": len(frames),
                        "evaluated_candidates": evaluated, "qualifying_candidates": qualifying, "tracks": tracks,
                        "strongest_near_misses": near, "parent_numerical_quality": parent_quality, "verdict": verdict}
        save_json(output / (arm_id + "_frames.json"), {"schema": "native_local_junction_frames_v1", "frames": frames})
        np.savez_compressed(output / (arm_id + "_final_witness.npz"), points=graph.world_sites,
                            volumes=graph.volumes, current_y=current["current_y"], current_i=current["current_i"],
                            center=center)
        arms[arm_id]["frames_sha256"] = file_sha(output / (arm_id + "_frames.json"))
        arms[arm_id]["final_witness_sha256"] = file_sha(output / (arm_id + "_final_witness.npz"))
        print(f"MEASURE {arm_id}: evaluated={evaluated} qualifying={qualifying} longest_track={tracks['maximum_consecutive_length']} verdict={verdict}", flush=True)
    persistent = [name for name, arm in arms.items() if arm["tracks"]["persistent"]]
    result = {"schema": "native_local_junction_analysis_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "VALID_MEASUREMENT_NUMERICAL_QUALITY_BOUND" if not persistent else "CANDIDATE_NUMERICAL_CONFIRMATION_REQUIRED",
              "source_hashes": hashes(), "spec_sha256": file_sha(SPEC_PATH), "calibration": calibration,
              "arm_count": len(arms), "frame_count": sum(a["frames"] for a in arms.values()),
              "evaluated_candidates": sum(a["evaluated_candidates"] for a in arms.values()),
              "qualifying_candidates": sum(a["qualifying_candidates"] for a in arms.values()),
              "persistent_arm_ids": persistent, "arms": arms,
              "interpretation": "Local paired native graph-current geometry only; formal native physics inference remains bound by parent endpoint-gradient failure."}
    save_json(output / "analysis.json", result)
    print(f"{result['status']}: frames={result['frame_count']} evaluated={result['evaluated_candidates']} qualifying={result['qualifying_candidates']} persistent={persistent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
