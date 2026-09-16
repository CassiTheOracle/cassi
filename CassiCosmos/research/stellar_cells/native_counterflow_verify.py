"""Independently audit counterflow artifacts; imports no measurement implementation."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "research/stellar_cells/native_counterflow_spec.json"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw_array(directory, meta, width=1):
    data = (directory / meta["path"]).read_bytes()
    require(hashlib.sha256(data).hexdigest() == meta["sha256"] and len(data) == meta["bytes"], "stored blob identity")
    raw = gzip.decompress(data)
    require(hashlib.sha256(raw).hexdigest() == meta["raw_sha256"] and len(raw) == meta["raw_bytes"], "decoded blob identity")
    values = np.frombuffer(raw, dtype="<u4" if meta["dtype"] == "uint32" else "<f4")
    require(values.size == meta["count"] and np.isfinite(values).all(), "blob shape/finite")
    return values.reshape(-1, width).astype(np.float64) if width > 1 else values


def mismatch_count(actual, expected, atol=1e-10, rtol=1e-10):
    return int(np.count_nonzero(np.abs(np.asarray(actual) - np.asarray(expected)) > atol + rtol * np.abs(expected)))


def audit_geometry(sites, jy, ji, volumes, center, radius, spacing, geometry, criteria):
    comparisons = 0
    def same(actual, expected, label):
        nonlocal comparisons
        if expected is None:
            require(actual is None, label + " missingness")
            comparisons += 1
            return
        require(actual is not None and mismatch_count(actual, expected) == 0, label)
        comparisons += np.asarray(expected).size
    relative = sites - center
    inside = np.linalg.norm(relative, axis=1) <= radius
    weights, support = [], []
    for current in (jy, ji):
        norm = np.linalg.norm(current, axis=1)
        weight = volumes * norm
        maximum = float(weight[inside].max()) if inside.any() else 0.0
        active = inside & (norm > criteria["current_floor"]) & (weight >= maximum * criteria["site_weight_relative_floor"]) if maximum > 0 else np.zeros(inside.size, bool)
        weights.append(weight)
        support.append(active)
    combined = np.where(support[0], weights[0], 0) + np.where(support[1], weights[1], 0)
    if combined.sum() == 0:
        require(geometry["axis"] is None and not geometry["detected"] and geometry["resolved_slice_count"] == 0, "zero-current geometry must not detect")
        return {"comparisons": 3, "winding_comparisons": 0, "zero_current": True}
    active = combined > 0
    centroid = np.average(relative[active], axis=0, weights=combined[active])
    centered = relative[active] - centroid
    covariance = (centered * combined[active, None]).T @ centered / combined[active].sum()
    eigenvalues = np.linalg.eigvalsh(covariance)
    chosen = 2 if eigenvalues[2] - eigenvalues[1] >= eigenvalues[1] - eigenvalues[0] else 0
    axis = np.asarray(geometry["axis"])
    same(np.dot(axis, axis), 1., "axis normalization")
    same(covariance @ axis, eigenvalues[chosen] * axis, "selected covariance eigenvector")
    same(geometry["covariance"], covariance, "current covariance")
    same(geometry["covariance_center"], centroid + center, "covariance center")
    basis = np.array([geometry["transverse_u"], geometry["transverse_v"], axis])
    same(basis @ basis.T, np.eye(3), "orthonormal frame")
    same(np.linalg.det(basis), 1., "right-handed frame")
    z = relative @ axis
    boundaries = np.linspace(-radius, radius, 9)
    centers = (boundaries[:-1] + boundaries[1:]) / 2
    resolved, separations, channel_centers, channel_means, channel_coherences = [], [], [[], []], [[], []], [[], []]
    for index, record in enumerate(geometry["slices"]):
        in_bin = (z >= boundaries[index]) & ((z < boundaries[index + 1]) if index < 7 else (z <= boundaries[index + 1]))
        stats = []
        for component, suffix, current in ((0, "y", jy), (1, "i", ji)):
            mask = support[component] & in_bin
            if not mask.any():
                for key in ("centroid", "width", "effective_n", "mean_current", "coherence"):
                    same(record[key + "_" + suffix], None, key)
                stats.append(None)
                channel_centers[component].append(None)
                channel_means[component].append(None)
                channel_coherences[component].append(None)
                continue
            w = weights[component][mask]
            point = np.average(sites[mask], axis=0, weights=w)
            delta = sites[mask] - point
            transverse = delta - (delta @ axis)[:, None] * axis
            width = np.sqrt(np.average(np.sum(transverse**2, axis=1), weights=w))
            neff = w.sum()**2 / np.sum(w**2)
            mean = np.average(current[mask], axis=0, weights=w)
            coherence = np.linalg.norm(mean) / np.average(np.linalg.norm(current[mask], axis=1), weights=w)
            for key, value in (("centroid", point), ("width", width), ("effective_n", neff), ("mean_current", mean), ("coherence", coherence)):
                same(record[key + "_" + suffix], value, f"slice {index} {key}_{suffix}")
            stats.append((point, width, neff))
            channel_centers[component].append(point)
            channel_means[component].append(mean)
            channel_coherences[component].append(coherence)
        if any(s is None for s in stats):
            separation, vector, pair = None, None, False
        else:
            vector = stats[1][0] - stats[0][0]
            vector -= np.dot(vector, axis) * axis
            separation = np.linalg.norm(vector)
            pair = bool(min(stats[0][2], stats[1][2]) >= criteria["effective_sites_min"]
                        and (2 * radius / 8) / spacing >= criteria["slice_width_over_spacing_min"]
                        and separation / spacing >= criteria["separation_over_spacing_min"]
                        and separation > 0 and separation >= np.hypot(stats[0][1], stats[1][1]) * criteria["separation_over_width_min"])
        same(record["separation"], separation, "channel separation")
        require(record["resolved"] == pair, "resolved pair predicate")
        comparisons += 1
        resolved.append(pair)
        separations.append(vector)
    best, run = [], []
    for index, value in enumerate(resolved):
        run = run + [index] if value else []
        if len(run) > len(best):
            best = run.copy()
    require(geometry["resolved_slice_count"] == sum(resolved) and geometry["consecutive_resolved_count"] == len(best), "resolved run count")
    comparisons += 2
    winding_comparisons = 0
    if len(best) >= 2:
        angles = np.array([np.arctan2(np.dot(separations[j], basis[1]), np.dot(separations[j], basis[0])) for j in best])
        unwrapped = np.unwrap(angles)
        signed = (unwrapped[-1] - unwrapped[0]) / (2 * np.pi)
        same(geometry["winding"]["winding_signed_turns"], signed, "signed spatial winding")
        same(geometry["winding_turns"], abs(signed), "absolute spatial winding")
        same(geometry["winding"]["unwrapped_separation_angles"], unwrapped, "unwrapped spatial angle")
        winding_comparisons = 2 + len(best)
    for index, record in enumerate(geometry["slices"]):
        for component, suffix in ((0, "y"), (1, "i")):
            points = channel_centers[component]
            tangent = None
            if points[index] is not None:
                lo = index - 1 if index > 0 and points[index - 1] is not None else index
                hi = index + 1 if index < 7 and points[index + 1] is not None else index
                if hi > lo:
                    derivative = points[hi] - points[lo]
                    norm = np.linalg.norm(derivative)
                    if norm > 0:
                        tangent = derivative / norm
                        if np.dot(tangent, axis) < 0:
                            tangent *= -1
            mean = channel_means[component][index]
            alignment = abs(np.dot(mean / np.linalg.norm(mean), tangent)) if tangent is not None and mean is not None and np.linalg.norm(mean) > 0 else None
            same(record["tangent_alignment_" + suffix], alignment, "current/tangent alignment")
    return {"comparisons": int(comparisons), "winding_comparisons": winding_comparisons, "zero_current": False}


def audit_native_endpoints(directory, receipt, summary, spec):
    """Recompute both endpoint discrepancies, including failures, from raw CSR."""
    first = receipt["snapshots"][0]["files"]
    positions = raw_array(directory, first["sites"], 4)[:, :3].astype(float)
    volumes = np.maximum(np.abs(raw_array(directory, first["site_vol"]).astype(float)), .005)
    offsets = raw_array(directory, first["offsets"]).astype(np.int64)
    neighbor = raw_array(directory, first["neighbors"]).astype(np.int64)
    count = volumes.size
    row = np.repeat(np.arange(count), np.diff(offsets))
    period = 2 * np.asarray(receipt["config"]["extents"])
    displacement = positions[neighbor] - positions[row]
    displacement -= period * np.floor(displacement / period + .5)
    distance = np.linalg.norm(displacement, axis=1)
    direction = displacement / distance[:, None]
    normal = np.broadcast_to(np.eye(3) * float(np.float32(1e-6)), (count, 3, 3)).copy()
    np.add.at(normal, row, direction[:, :, None] * direction[:, None, :])
    valid = np.abs(np.linalg.det(normal)) > 1e-12
    endpoint_rows = []
    for snapshot, saved in zip((receipt["snapshots"][0], receipt["snapshots"][-1]), summary["integrity"]["endpoint_checks"]):
        files = snapshot["files"]
        channels = {}
        for suffix in ("y", "i"):
            field = raw_array(directory, files["site_psi_" + suffix]).astype(float)
            difference = field[neighbor] - field[row]
            rhs = np.zeros((count, 3))
            np.add.at(rhs, row, (difference / distance)[:, None] * direction)
            gradient = np.zeros((count, 3))
            gradient[valid] = np.linalg.solve(normal[valid], rhs[valid, :, None])[:, :, 0]
            laplacian = np.bincount(row, weights=volumes[row]**(2 / 3) * difference / distance, minlength=count)
            for role, value, width in (("grad_" + suffix, gradient, 4), ("lap_" + suffix, laplacian, 1)):
                reference = raw_array(directory, files[role], width)
                if width == 4:
                    reference = reference[:, :3]
                kind = "gradient" if width == 4 else "lap"
                tolerance = spec["verification"][kind + "_atol"] + spec["verification"][kind + "_rtol"] * np.abs(reference)
                error = np.abs(value - reference)
                bad = error > tolerance
                bad_sites = np.flatnonzero(np.any(bad, axis=1) if width == 4 else bad)
                mismatches = int(np.count_nonzero(bad))
                require(mismatches == saved["channels"][role]["mismatches"], "independent endpoint disagreement count")
                channels[role] = {
                    "comparisons": int(error.size), "mismatches": mismatches,
                    "max_abs_error": float(error.max()), "bad_site_ids": bad_sites.tolist(),
                    "bad_site_degrees": np.diff(offsets)[bad_sites].tolist(),
                    "bad_site_condition_numbers": np.linalg.cond(normal[bad_sites]).tolist() if bad_sites.size else [],
                }
        endpoint_rows.append({"step": snapshot["step"], "channels": channels})
    mismatches = sum(c["mismatches"] for e in endpoint_rows for c in e["channels"].values())
    require(mismatches == summary["integrity"]["endpoint_mismatches"], "endpoint total")
    expected_status = "VALID" if mismatches == 0 and summary["integrity"]["balance_mismatches"] == 0 else "INVALID"
    require(summary["status"] == expected_status, "quality failure must remain a failure")
    if expected_status == "INVALID":
        require(summary["radial_verdict"] == "INCONCLUSIVE" and summary["helical_verdict"] == "INCONCLUSIVE", "failed quality cannot yield a science verdict")
    return {"comparisons": count * 16, "mismatches": mismatches, "endpoints": endpoint_rows}


def audit_arm(name, summary, output, source, spec):
    directory = source / name
    receipt_path = directory / "receipt.json"
    require(digest(receipt_path) == summary["source_receipt_sha256"], "source receipt identity")
    receipt = load_json(receipt_path)
    arm_output = output / name
    require(load_json(arm_output / "summary.json") == summary, "arm summary vs analysis")
    for path, expected in summary["artifacts"].items():
        require(digest(arm_output / path) == expected, "analysis artifact identity " + path)
    frames = load_json(arm_output / "frames.json")["frames"]
    require(len(frames) == len(receipt["snapshots"]) == summary["snapshots"], "frame coverage")
    first, last = receipt["snapshots"][0]["files"], receipt["snapshots"][-1]["files"]
    offsets = raw_array(directory, first["offsets"]).astype(np.int64)
    neighbors = raw_array(directory, first["neighbors"]).astype(np.int64)
    count = len(offsets) - 1
    rows = np.repeat(np.arange(count), np.diff(offsets))
    canonical = rows < neighbors
    left, right = rows[canonical], neighbors[canonical]
    sites = raw_array(directory, last["sites"], 4)[:, :3] - np.asarray(summary["config"]["extents"])
    volumes = np.maximum(np.abs(raw_array(directory, last["site_vol"]).astype(float)), .005)
    period = 2 * np.asarray(summary["config"]["extents"])
    delta = sites[right] - sites[left]
    delta -= period * np.floor(delta / period + .5)
    reverse = -delta.copy()
    # Native ties are evaluated independently in each directed CSR row.
    reverse -= period * np.floor(reverse / period + .5)
    distance = np.linalg.norm(delta, axis=1)
    c = summary["coefficients"]
    cfg = receipt["config"]
    require(cfg == summary["config"], "native receipt configuration")
    cell_volume = float(np.prod(period)) / count
    native_h = cell_volume ** (1 / 3)
    expected_coefficients = {
        "c2": float(np.float32(native_h**2 * cfg["c2_multiplier"])),
        "phi": float(np.float32((1 + np.sqrt(5)) / 2)),
        "omega2": float(np.float32(20 * cfg["conversion_multiplier"])),
        "mass_scale": float(np.float32(.001 * cell_volume * cfg["mass_source_multiplier"])),
        "spacing": native_h,
    }
    require(c == expected_coefficients, "native float32 coefficient reconstruction")
    expected_powers, expected_currents = [], []
    with np.load(arm_output / "final_current_witness.npz") as archive:
        witness = {key: archive[key] for key in archive.files}
    require(np.array_equal(left, witness["edge_i"]) and np.array_equal(right, witness["edge_j"]), "canonical edges")
    scalar_comparisons = 0
    for suffix, weight in (("y", 1.0), ("i", c["phi"])):
        psi = raw_array(directory, last["site_psi_" + suffix]).astype(float)
        momentum = raw_array(directory, last["site_pi_" + suffix]).astype(float)
        power = -(weight * c["c2"] / (2 * distance)) * (psi[right] - psi[left]) * (momentum[left] + momentum[right])
        current = np.zeros((count, 3))
        np.add.at(current, left, power[:, None] * delta)
        np.add.at(current, right, -power[:, None] * reverse)
        current /= 2 * volumes[:, None]
        require(mismatch_count(witness["edge_power_" + suffix], power) == 0, "independent native bond power")
        require(mismatch_count(witness["current_" + suffix], current) == 0, "independent native current first moment")
        scalar_comparisons += power.size + current.size
        expected_powers.append(power)
        expected_currents.append(current)
    position = raw_array(directory, last["pos"], 4)
    center = np.average(position[:, :3], axis=0, weights=position[:, 3])
    require(mismatch_count(frames[-1]["center"], center) == 0, "particle COM")
    r = np.linalg.norm(sites - center, axis=1)
    cut_comparisons = 0
    for saved in frames[-1]["radial"]:
        mask = r <= saved["radius_over_R"] * summary["config"]["radius"]
        crossing = mask[left] != mask[right]
        require(saved["crossing_edges"] == int(crossing.sum()), "radial crossing count")
        direction = np.where(mask[left[crossing]], 1, -1)
        for suffix, power in zip(("Y", "I"), expected_powers):
            oriented = direction * power[crossing]
            for key, expected in ((suffix + "_out", np.sum(np.maximum(oriented, 0))), (suffix + "_in", np.sum(np.maximum(-oriented, 0)))):
                require(mismatch_count(saved[key], expected) == 0, "independent radial cut power")
                cut_comparisons += 1
    geometry = audit_geometry(sites, *expected_currents, volumes, center, summary["config"]["radius"], c["spacing"], frames[-1]["geometry"], spec["geometry"])
    final = [f for f in frames if 24 - 1e-9 <= f["t"] <= 32 + 1e-9]
    radial_index = spec["radial"]["radii_over_R"].index(.5)
    opposed = sum(f["radial"][radial_index]["strong_opposition"] for f in final)
    detected = sum(f["geometry"]["detected"] for f in final)
    require(summary["final_window"]["samples"] == len(final) and summary["final_window"]["radial_opposed_samples"] == opposed and summary["final_window"]["helix_detected_samples"] == detected, "primary denominator and numerator")
    require(summary["all_time_helix_detected_samples"] == sum(f["geometry"]["detected"] for f in frames), "all-time trigger count")
    balance_count = sum(f["energy"]["balance_comparisons"] for f in frames)
    require(balance_count == count * len(frames) == summary["integrity"]["balance_comparisons"], "pointwise conservation attempts")
    endpoint_count = sum(cmp["comparisons"] for e in summary["integrity"]["endpoint_checks"] for cmp in e["channels"].values())
    require(endpoint_count == count * 16, "both GPU endpoint derivative comparison counts")
    endpoint_audit = audit_native_endpoints(directory, receipt, summary, spec)
    spatial_ratio = (2 * cfg["radius"] / spec["geometry"]["slices"]) / c["spacing"]
    require(mismatch_count(summary["final_window"]["axial_slice_width_over_spacing"], spatial_ratio) == 0, "axial sampling ratio")
    spatial_eligible = spatial_ratio >= spec["geometry"]["slice_width_over_spacing_min"]
    require(summary["final_window"]["helical_spatial_resolution_eligible"] == spatial_eligible, "spatial sampling eligibility")
    if not spatial_eligible:
        require(summary["helical_verdict"] == "INCONCLUSIVE", "underresolved geometry cannot establish absence")
    result = {"arm": name, "bond_and_current_comparisons": scalar_comparisons, "radial_power_comparisons": cut_comparisons,
              "geometry": geometry, "source_node_balance_comparisons": balance_count, "source_endpoint_comparisons": endpoint_count,
              "independent_endpoint_audit": endpoint_audit,
              "snapshot_count": len(frames), "final_samples": len(final), "radial_opposed": opposed, "helical_detected": detected}
    return result, witness, expected_powers, left, right


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    spec = load_json(SPEC)
    output = args.output or ROOT / spec["output"]
    source = ROOT / spec["source_campaign"]
    analysis = load_json(output / "analysis.json")
    require(analysis["status"] in ("VALID", "INVALID"), "unknown measurement quality state")
    require(digest(source / "campaign.json") == spec["source_campaign_sha256"] == analysis["source_campaign_sha256"], "parent campaign binding")
    require(digest(source / "analysis.json") == spec["source_analysis_sha256"] == analysis["source_analysis_sha256"], "parent evidence binding")
    for name, expected in {**analysis["source_hashes"], **analysis["native_operator_hashes"]}.items():
        require(digest(ROOT / name) == expected, "source changed: " + name)
    require(digest(output / "calibration.json") == analysis["calibration_sha256"], "calibration identity")
    calibration = load_json(output / "calibration.json")
    require(calibration["status"] == "PASS" and calibration["source_hashes"] == analysis["source_hashes"], "calibrated source closure")
    with np.load(output / "analytic_helix_input.npz") as fixture:
        require(digest(output / "analytic_helix_input.npz") == calibration["analytic_helix_input_sha256"], "analytic calibration inputs")
        analytic = audit_geometry(fixture["sites"], fixture["current_y"], fixture["current_i"], fixture["volumes"], np.zeros(3),
                                  spec["calibration"]["geometry_radius"], spec["calibration"]["geometry_spacing"],
                                  calibration["geometry"]["helical_counterflow"]["measurement"], spec["geometry"])
    require(analytic["winding_comparisons"] > 0, "independent winding check never fired")
    audits, firing = [], None
    require(set(analysis["arms"]) == set(spec["arm_ids"]), "complete arm coverage")
    for name in spec["arm_ids"]:
        summary = analysis["arms"][name]
        audit, witness, expected, left, right = audit_arm(name, summary, output, source, spec)
        audits.append(audit)
        if firing is None and not summary["config"]["freeze_field"] and np.max(np.abs(expected[0])) > 1e-8:
            index = int(np.argmax(np.abs(expected[0])))
            modified = {key: value.copy() for key, value in witness.items()}
            modified["edge_power_y"][index] *= -1
            mutation_path = output / "mutation_edge_power.npz"
            np.savez_compressed(mutation_path, **modified)
            with np.load(mutation_path) as reread:
                mutated = reread["edge_power_y"]
                formula_bad = mismatch_count(mutated, expected[0])
                divergence = np.zeros(witness["source_power_by_site"].size)
                total = mutated + reread["edge_power_i"]
                np.add.at(divergence, left, total)
                np.add.at(divergence, right, -total)
                balance = reread["energy_derivative_by_site"] + divergence - reread["source_power_by_site"]
                scale = np.maximum.reduce([np.abs(reread["energy_derivative_by_site"]), np.abs(divergence), np.abs(reread["source_power_by_site"])])
                balance_bad = int(np.count_nonzero(np.abs(balance) > 1e-9 + 1e-9 * scale))
            require(formula_bad == 1 and balance_bad == 2, "real-artifact numeric mutation must fire at one bond/two nodes")
            original = output / name / "final_current_witness.npz"
            require(digest(original) == summary["artifacts"]["final_current_witness.npz"], "mutation changed original")
            firing = {"source_arm": name, "source_artifact_sha256": digest(original), "mutated_artifact_sha256": digest(mutation_path),
                      "mutated_edge_index": index, "formula_comparisons": int(expected[0].size), "formula_mismatches": formula_bad,
                      "node_balance_comparisons": int(divergence.size), "node_balance_mismatches": balance_bad,
                      "mutation": "Sign reversal of one actually measured nonzero Y bond power; fresh saved artifact identity accepted before numeric checks.",
                      "original_unchanged": True}
        print(f"VERIFY {name}: {audit['bond_and_current_comparisons']} bond/current values, {audit['geometry']['comparisons']} geometry comparisons", flush=True)
    require(firing is not None, "no genuine nonzero artifact available for firing check")
    triggers = [name for name in spec["primary_arm_ids"] if analysis["arms"][name]["final_window"]["radial_persistent"] or analysis["arms"][name]["all_time_helix_detected_samples"]]
    require(triggers == analysis["dense_triggered_arm_ids"] and bool(triggers) == analysis["dense_confirmation_required"], "dense confirmation trigger")
    quality_valid = all(a["independent_endpoint_audit"]["mismatches"] == 0 for a in audits)
    require((analysis["status"] == "VALID") == quality_valid, "overall quality classification")
    audit_status = "PASS" if quality_valid else "VERIFIED_INCONCLUSIVE"
    result = {"schema": "native_counterflow_independent_verification_v1", "status": audit_status,
              "measurement_quality": analysis["status"], "analysis_sha256": digest(output / "analysis.json"),
              "verifier_sha256": digest(__file__), "arm_count": len(audits), "audits": audits, "analytic_geometry": analytic,
              "firing": firing, "dense_triggered_arm_ids": triggers,
              "counts": {"bond_and_current_comparisons": sum(a["bond_and_current_comparisons"] for a in audits),
                         "radial_power_comparisons": sum(a["radial_power_comparisons"] for a in audits),
                         "geometry_comparisons": sum(a["geometry"]["comparisons"] for a in audits) + analytic["comparisons"],
                         "source_node_balance_comparisons": sum(a["source_node_balance_comparisons"] for a in audits),
                         "source_endpoint_comparisons": sum(a["source_endpoint_comparisons"] for a in audits)},
              "scope": "Independent raw final-state bond/current/cut/geometry recalculation on every arm plus analytic winding and actual-artifact mutation; hashes/counts bind all-time producer balance and both GPU endpoint comparisons."}
    (output / "verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(audit_status + " " + json.dumps(result["counts"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
