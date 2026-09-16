"""Independently verify local-junction artifacts without importing their detector."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "research/stellar_cells/native_local_junction_spec.json"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(value, message):
    if not value:
        raise ValueError(message)


def raw(directory, meta, width=1):
    stored = (directory / meta["path"]).read_bytes()
    require(len(stored) == meta["bytes"] and hashlib.sha256(stored).hexdigest() == meta["sha256"], "stored blob identity")
    decoded = gzip.decompress(stored)
    require(len(decoded) == meta["raw_bytes"] and hashlib.sha256(decoded).hexdigest() == meta["raw_sha256"], "decoded blob identity")
    values = np.frombuffer(decoded, dtype="<u4" if meta["dtype"] == "uint32" else "<f4")
    return values.reshape(-1, width).astype(float) if width > 1 else values.astype(float)


def axis(value):
    value = value / np.linalg.norm(value)
    pivot = int(np.argmax(np.abs(value)))
    return -value if value[pivot] < 0 else value


def stats(points, current, weights, selected):
    if selected.size == 0:
        return None
    weight = weights[selected]
    total, square = weight.sum(), np.sum(weight**2)
    if total <= 0 or square <= 0:
        return None
    centroid = np.average(points[selected], axis=0, weights=weight)
    centered = points[selected] - centroid
    covariance = (centered * weight[:, None]).T @ centered / total
    eigenvalues, eigenvectors = np.linalg.eigh((covariance + covariance.T) / 2)
    direction = axis(eigenvectors[:, -1])
    mean = np.average(current[selected], axis=0, weights=weight)
    mean_norm = np.linalg.norm(mean)
    mean_speed = np.average(np.linalg.norm(current[selected], axis=1), weights=weight)
    return {"site_count": int(selected.size), "weight_sum": float(total), "effective_n": float(total**2 / square),
            "centroid": centroid.tolist(), "covariance_eigenvalues": eigenvalues.tolist(), "axis": direction.tolist(),
            "linearity_ratio": float(eigenvalues[-1] / max(eigenvalues[-2], 1e-30)), "mean_current": mean.tolist(),
            "coherence": float(mean_norm / mean_speed) if mean_speed > 0 else None,
            "axis_alignment": abs(float(np.dot(mean / mean_norm, direction))) if mean_norm > 0 else None}


def independent_frame(points, jy, ji, volumes, center, radius, h, c):
    inside = np.linalg.norm(points - center, axis=1) <= radius * c["sphere_radius_over_R"]
    currents = (jy, ji)
    norms = [np.linalg.norm(v, axis=1) for v in currents]
    weights = [volumes * v for v in norms]
    maxima = [float(w[inside].max()) if inside.any() else 0.0 for w in weights]
    if min(maxima) <= 0:
        return {"candidate_pool": 0, "ranked_centers": 0, "evaluated_centers": 0, "qualifying_count": 0,
                "component_weight_max": maxima, "candidates": []}
    score = np.sqrt(weights[0] / maxima[0] * weights[1] / maxima[1])
    pool = np.flatnonzero(inside & (score >= c["joint_score_min"]))
    ranked = pool[np.lexsort((pool, -score[pool]))]
    centers = []
    for site in ranked:
        if len(centers) == c["max_ranked_centers"]:
            break
        if all(np.linalg.norm(points[site] - points[other]) > c["nonmaximum_suppression_radius_over_h"] * h for other in centers):
            centers.append(int(site))
    tree = cKDTree(points)
    candidates = []
    for site in centers:
        neighborhood = np.asarray(tree.query_ball_point(points[site], c["neighborhood_radius_over_h"] * h), dtype=int)
        channels = [stats(points, currents[k], weights[k], neighborhood) for k in range(2)]
        reasons = []
        if neighborhood.size < c["minimum_sites"]:
            reasons.append("insufficient neighborhood sites")
        for label, data in zip(("Y", "I"), channels):
            if data is None:
                reasons.append(label + " channel unavailable")
                continue
            if data["effective_n"] < c["effective_sites_min"]: reasons.append(label + " effective support below threshold")
            if data["linearity_ratio"] < c["linearity_ratio_min"]: reasons.append(label + " channel is not line-like")
            if data["coherence"] is None or data["coherence"] < c["current_coherence_min"]: reasons.append(label + " current coherence below threshold")
            if data["axis_alignment"] is None or data["axis_alignment"] < c["current_axis_alignment_min"]: reasons.append(label + " current is not aligned with fitted channel")
        angle = distance = sy = si = centroid_distance = current_dot = None
        if all(data is not None for data in channels):
            ay, ai = np.asarray(channels[0]["axis"]), np.asarray(channels[1]["axis"])
            py, pi = np.asarray(channels[0]["centroid"]), np.asarray(channels[1]["centroid"])
            dot = float(np.dot(ay, ai))
            angle = float(np.degrees(np.arccos(np.clip(abs(dot), -1, 1))))
            denominator = 1 - dot**2
            if denominator > 1e-12:
                w = py - pi
                aw, bw = np.dot(ay, w), np.dot(ai, w)
                sy, si = float((dot * bw - aw) / denominator), float((bw - dot * aw) / denominator)
                distance = float(np.linalg.norm(py + sy * ay - pi - si * ai))
            centroid_distance = float(np.linalg.norm(py - pi))
            my, mi = np.asarray(channels[0]["mean_current"]), np.asarray(channels[1]["mean_current"])
            current_dot = float(np.dot(my / np.linalg.norm(my), mi / np.linalg.norm(mi)))
            if angle < c["crossing_angle_min_degrees"]: reasons.append("component lines are too parallel for an intersection")
            if distance is None or distance > c["line_closest_approach_max_over_h"] * h: reasons.append("fitted lines do not approach closely enough")
            if sy is None or max(abs(sy), abs(si)) > c["closest_parameter_abs_max_over_h"] * h: reasons.append("closest approach lies outside local fitted segments")
            if centroid_distance > c["centroid_distance_max_over_h"] * h: reasons.append("component centroids are too far apart")
        candidates.append({"center_site": site, "center": points[site].tolist(), "joint_score": float(score[site]),
                           "neighborhood_site_count": int(neighborhood.size), "Y": channels[0], "I": channels[1],
                           "crossing_angle_degrees": angle, "line_closest_approach": distance,
                           "line_closest_approach_over_h": None if distance is None else distance / h,
                           "closest_parameter_y_over_h": None if sy is None else sy / h,
                           "closest_parameter_i_over_h": None if si is None else si / h,
                           "centroid_distance_over_h": None if centroid_distance is None else centroid_distance / h,
                           "mean_current_dot": current_dot, "qualifying": not reasons, "reasons": reasons})
    return {"candidate_pool": int(pool.size), "ranked_centers": min(int(ranked.size), c["max_ranked_centers"]),
            "evaluated_centers": len(candidates), "qualifying_count": sum(x["qualifying"] for x in candidates),
            "component_weight_max": maxima, "candidates": candidates}


def compare(left, right, path="root"):
    if isinstance(left, dict):
        require(isinstance(right, dict) and set(left) == set(right), path + " keys")
        return sum(compare(left[k], right[k], path + "." + k) for k in left)
    if isinstance(left, list):
        require(isinstance(right, list) and len(left) == len(right), path + " length")
        return sum(compare(a, b, path + "[]") for a, b in zip(left, right))
    if isinstance(left, (float, int)) and not isinstance(left, bool):
        require(right is not None and abs(float(left) - float(right)) <= 1e-10 + 1e-10 * abs(float(right)), path)
        return 1
    require(left == right, path)
    return 1


def fixture(name, spec):
    h, radius = spec["calibration"]["spacing"], spec["calibration"]["radius"]
    coordinate = np.arange(-radius, radius + h / 2, h)
    points = np.stack(np.meshgrid(coordinate, coordinate, coordinate, indexing="ij"), axis=-1).reshape(-1, 3)
    sigma = spec["calibration"]["tube_sigma_over_h"] * h
    y = np.exp(-(points[:, 1]**2 + points[:, 2]**2) / (2 * sigma**2))
    i = np.exp(-(points[:, 0]**2 + points[:, 2]**2) / (2 * sigma**2))
    jy, ji = y[:, None] * [1., 0, 0], i[:, None] * [0., 1, 0]
    if name == "rotated_orthogonal_crossing":
        direction = np.array([1., 2., 3.]) / np.sqrt(14)
        cross = np.array([[0, -direction[2], direction[1]], [direction[2], 0, -direction[0]], [-direction[1], direction[0], 0]])
        rotation = np.eye(3) + np.sin(.67) * cross + (1 - np.cos(.67)) * cross @ cross
        points, jy, ji = points @ rotation.T, jy @ rotation.T, ji @ rotation.T
    elif name == "parallel_separated":
        y = np.exp(-((points[:, 1] + h)**2 + points[:, 2]**2) / (2 * sigma**2))
        i = np.exp(-((points[:, 1] - h)**2 + points[:, 2]**2) / (2 * sigma**2))
        jy, ji = y[:, None] * [1., 0, 0], i[:, None] * [-1., 0, 0]
    elif name == "single_component": ji[:] = 0
    elif name == "isotropic_radial":
        norm = np.linalg.norm(points, axis=1)
        unit = np.divide(points, norm[:, None], out=np.zeros_like(points), where=norm[:, None] > 0)
        envelope = np.exp(-norm**2 / 2)
        jy, ji = envelope[:, None] * unit, -envelope[:, None] * unit
    elif name == "zero_current": jy[:], ji[:] = 0, 0
    return points, jy, ji, np.full(points.shape[0], h**3)


def reconstruct_current(directory, receipt, coeff):
    files = receipt["snapshots"][-1]["files"]
    sites = raw(directory, files["sites"], 4)[:, :3] - np.asarray(receipt["config"]["extents"])
    volume = np.maximum(np.abs(raw(directory, files["site_vol"])), .005)
    offsets = raw(directory, files["offsets"]).astype(int)
    neighbors = raw(directory, files["neighbors"]).astype(int)
    rows = np.repeat(np.arange(volume.size), np.diff(offsets))
    mask = rows < neighbors
    left, right = rows[mask], neighbors[mask]
    period = 2 * np.asarray(receipt["config"]["extents"])
    displacement = sites[right] - sites[left]
    displacement -= period * np.floor(displacement / period + .5)
    reverse = -displacement.copy()
    reverse -= period * np.floor(reverse / period + .5)
    distance = np.linalg.norm(displacement, axis=1)
    currents = []
    powers = []
    for suffix, weight in (("y", 1.), ("i", coeff["phi"])):
        field = raw(directory, files["site_psi_" + suffix])
        momentum = raw(directory, files["site_pi_" + suffix])
        power = -weight * coeff["c2"] * (field[right] - field[left]) * (momentum[left] + momentum[right]) / (2 * distance)
        current = np.zeros((volume.size, 3))
        np.add.at(current, left, power[:, None] * displacement)
        np.add.at(current, right, -power[:, None] * reverse)
        current /= 2 * volume[:, None]
        powers.append(power); currents.append(current)
    position = raw(directory, files["pos"], 4).astype(np.float32)
    center = np.average(position[:, :3], axis=0, weights=position[:, 3])
    return sites, volume, currents, powers, center


def track_summary(frames, h, criteria):
    active, completed = [], []
    for frame_index, frame in enumerate(frames):
        candidates = [c for c in frame["junctions"]["candidates"] if c["qualifying"]]
        available = set(range(len(candidates))); following = []
        for track in active:
            prior = track[-1]; matches = []
            for index in available:
                candidate = candidates[index]
                distance = np.linalg.norm(np.asarray(prior["center"]) - candidate["center"])
                cosine = min(abs(np.dot(prior[k]["axis"], candidate[k]["axis"])) for k in ("Y", "I"))
                if distance <= criteria["match_center_distance_max_over_h"] * h and cosine >= criteria["axis_cosine_abs_min"]:
                    matches.append((distance, candidate["center_site"], index))
            if matches:
                index = min(matches)[2]; available.remove(index); following.append(track + [candidates[index]])
            else: completed.append(track)
        following.extend([[candidates[index]] for index in sorted(available, key=lambda x: candidates[x]["center_site"])])
        active = following
    completed.extend(active)
    lengths = sorted((len(x) for x in completed), reverse=True)
    return len(completed), lengths[0] if lengths else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = load_json(SPEC_PATH)
    output = args.output or ROOT / spec["output"]
    analysis = load_json(output / "analysis.json")
    require(analysis["spec_sha256"] == sha(SPEC_PATH), "frozen spec identity")
    for name, digest in analysis["source_hashes"].items(): require(sha(ROOT / name) == digest, "source identity " + name)
    calibration_comparisons = 0
    for name, expected in spec["calibration"]["cases"].items():
        points, jy, ji, volume = fixture(name, spec)
        measured = independent_frame(points, jy, ji, volume, np.zeros(3), spec["calibration"]["radius"], spec["calibration"]["spacing"], spec["candidate"])
        calibration_comparisons += compare(measured, analysis["calibration"][name]["measurement"], "calibration." + name)
        require((measured["qualifying_count"] > 0) == expected, "calibration classification " + name)
    current_comparisons = candidate_comparisons = frame_count = 0
    mutation = None
    campaign = load_json(ROOT / spec["source_campaign"] / "campaign.json")
    for arm_id in spec["arm_ids"]:
        arm, directory = analysis["arms"][arm_id], ROOT / spec["source_campaign"] / arm_id
        require(sha(output / (arm_id + "_frames.json")) == arm["frames_sha256"], "frame artifact identity")
        require(sha(output / (arm_id + "_final_witness.npz")) == arm["final_witness_sha256"], "witness identity")
        receipt = load_json(directory / "receipt.json")
        sites, volume, currents, powers, center = reconstruct_current(directory, receipt, arm["coefficients"])
        with np.load(output / (arm_id + "_final_witness.npz")) as saved:
            for key, expected in (("points", sites), ("volumes", volume), ("current_y", currents[0]), ("current_i", currents[1]), ("center", center)):
                actual = saved[key]
                require(np.all(np.abs(actual - expected) <= 1e-10 + 1e-10 * np.abs(expected)), "current witness " + key)
                current_comparisons += actual.size
        frames = load_json(output / (arm_id + "_frames.json"))["frames"]
        require(len(frames) == arm["frames"], "frame count")
        final = independent_frame(sites, currents[0], currents[1], volume, center, arm["config"]["radius"], arm["coefficients"]["spacing"], spec["candidate"])
        candidate_comparisons += compare(final, frames[-1]["junctions"], arm_id + ".final")
        total_tracks, maximum = track_summary(frames, arm["coefficients"]["spacing"], spec["persistence"])
        require(total_tracks == arm["tracks"]["track_count"] and maximum == arm["tracks"]["maximum_consecutive_length"], "track reconstruction")
        require(sum(f["junctions"]["evaluated_centers"] for f in frames) == arm["evaluated_candidates"], "candidate denominator")
        require(sum(f["junctions"]["qualifying_count"] for f in frames) == arm["qualifying_candidates"], "candidate numerator")
        frame_count += len(frames)
        if mutation is None and final["evaluated_centers"]:
            path = output / "mutation_zero_i_current.npz"
            np.savez_compressed(path, points=sites, volumes=volume, current_y=currents[0], current_i=np.zeros_like(currents[1]), center=center)
            with np.load(path) as changed:
                negative = independent_frame(changed["points"], changed["current_y"], changed["current_i"], changed["volumes"], changed["center"], arm["config"]["radius"], arm["coefficients"]["spacing"], spec["candidate"])
            require(negative["candidate_pool"] == 0 and negative["evaluated_centers"] == 0, "mutation must fire component-support gate")
            require(sha(output / (arm_id + "_final_witness.npz")) == arm["final_witness_sha256"], "mutation changed original")
            mutation = {"source_arm": arm_id, "source_sha256": arm["final_witness_sha256"], "mutated_sha256": sha(path),
                        "original_candidate_pool": final["candidate_pool"], "mutated_candidate_pool": 0,
                        "original_evaluated_centers": final["evaluated_centers"], "mutated_evaluated_centers": 0,
                        "original_unchanged": True, "mutation": "Set the actual retained final-state Yin current vectors to zero in a copied witness."}
        print(f"VERIFY {arm_id}: current_values={sites.size + volume.size + currents[0].size + currents[1].size + center.size} final_candidates={final['evaluated_centers']}", flush=True)
    require(mutation is not None, "firing mutation unavailable")
    require(frame_count == analysis["frame_count"] and set(analysis["arms"]) == set(spec["arm_ids"]), "registered coverage")
    receipt = {"schema": "native_local_junction_verification_v1", "status": "PASS",
               "analysis_sha256": sha(output / "analysis.json"), "verifier_sha256": sha(__file__),
               "calibration_comparisons": calibration_comparisons, "current_witness_comparisons": current_comparisons,
               "final_candidate_comparisons": candidate_comparisons, "frame_count": frame_count,
               "candidate_denominator": analysis["evaluated_candidates"], "candidate_numerator": analysis["qualifying_candidates"],
               "persistent_arm_ids": analysis["persistent_arm_ids"], "mutation": mutation,
               "interpretation": "Independent artifact/current/final-candidate/track verification; does not override parent numerical-quality bound."}
    (output / "verification.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("PASS " + json.dumps({k: receipt[k] for k in ("calibration_comparisons", "current_witness_comparisons", "final_candidate_comparisons", "frame_count", "candidate_denominator", "candidate_numerator")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
