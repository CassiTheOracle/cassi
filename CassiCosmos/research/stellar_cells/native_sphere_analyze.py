"""Independently measure the frozen native-sphere campaign from lossless GPU arrays."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PHI = (1.0 + math.sqrt(5.0)) / 2.0
FIELD = ("site_psi_y", "site_psi_i", "site_pi_y", "site_pi_i")
DERIVED = ("field_q", "site_eps")
WIDTHS = {"pos": 4, "vel": 4, "acc": 4, "sites": 4, "tree_sources": 8,
          "grad_y": 4, "grad_i": 4}
REQUIRED = ("pos", "vel", "acc", "sites", *FIELD, *DERIVED, "site_vol", "site_mass",
            "tree_sources", "tree_weights")
ENDPOINT = ("offsets", "neighbors", "lap_y", "lap_i", "grad_y", "grad_i")
IDENTITY = ("pos", "vel", "acc", "sites", "site_vol", *FIELD, *DERIVED)
# Registration binds particle/field bytes; GPU-built geometry and acceleration
# are diagnostics across independent launches, but geometry is fixed within an arm.
MATCHED_INITIAL = ("pos", "vel", *FIELD, *DERIVED)


class IntegrityError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IntegrityError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_value(value):
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def save_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(json_value(value), indent=2, allow_nan=False) + "\n", encoding="utf-8")


class BlobReader:
    def __init__(self, directory: Path, particles: int, sites: int, frozen: bool):
        self.directory, self.particles, self.sites = directory, particles, sites
        self.cache_roles = {"sites", "site_vol", "offsets", "neighbors"}
        if frozen:
            self.cache_roles.update((*FIELD, *DERIVED))
        self.cache: dict[str, tuple[dict, np.ndarray]] = {}
        self.declarations = 0
        self.verified_files: set[str] = set()
        self.decoded_elements = 0

    def load(self, role: str, item: dict) -> np.ndarray:
        self.declarations += 1
        require(role in REQUIRED or role in ENDPOINT, f"unknown role {role}")
        if role in self.cache and self.cache[role][0] == item:
            return self.cache[role][1]
        rel = Path(item["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, f"unsafe blob path {rel}")
        integer = role in ("offsets", "neighbors")
        dtype = "uint32" if integer else "float32"
        require(item["dtype"] == dtype and item["encoding"] == "gzip", f"{role}: dtype/encoding")
        count = item["count"]
        require(isinstance(count, int) and count > 0, f"{role}: element count")
        if role != "neighbors":
            records = self.particles if role in ("pos", "vel", "acc") else self.sites
            if role == "offsets":
                records += 1
            require(count == records * WIDTHS.get(role, 1), f"{role}: shape/count mismatch")
        data = (self.directory / rel).read_bytes()
        require(len(data) == item["bytes"] and sha(data) == item["sha256"], f"{role}: stored SHA256/size mismatch")
        raw = gzip.decompress(data)
        require(len(raw) == item["raw_bytes"] == count * 4 and sha(raw) == item["raw_sha256"],
                f"{role}: raw SHA256/size mismatch")
        array = np.frombuffer(raw, dtype="<u4" if integer else "<f4")
        if role in WIDTHS:
            array = array.reshape(-1, WIDTHS[role])
        require(bool(np.isfinite(array).all()), f"{role}: nonfinite authoritative state")
        self.verified_files.add(str(rel))
        self.decoded_elements += count
        if role in self.cache_roles:
            self.cache[role] = (dict(item), array)
        return array


def radii_at_quantiles(radius: np.ndarray, mass: np.ndarray) -> np.ndarray:
    order = np.argsort(radius)
    cumulative = np.cumsum(mass[order])
    return radius[order[np.searchsorted(cumulative, cumulative[-1] * np.array([.1, .5, .9]))]]


def radial_profile(radius, mass, site_radius, volume, q, epsilon, rho, deposited, scale) -> dict:
    edges = np.linspace(0.0, 2.0 * scale, 13)
    shell_volume = 4 * math.pi / 3 * np.diff(edges**3)
    particle_mass, _ = np.histogram(radius, bins=edges, weights=mass)
    site_volume, _ = np.histogram(site_radius, bins=edges, weights=volume)
    result = {"edges_r_over_R": edges / scale, "particle_mass": particle_mass,
              "particle_mass_density": particle_mass / shell_volume, "site_volume": site_volume,
              "site_count": np.histogram(site_radius, bins=edges)[0],
              "site_deposited_mass": np.histogram(site_radius, bins=edges, weights=deposited)[0],
              "outside_two_R_particle_mass": mass[radius > 2 * scale].sum()}
    for name, values in (("q", q), ("epsilon", epsilon), ("rho", rho)):
        weighted = np.histogram(site_radius, bins=edges, weights=values * volume)[0]
        result[name + "_volume_weighted"] = np.divide(weighted, site_volume,
            out=np.full(12, np.nan), where=site_volume > 0)
    result["positive_field_mass"] = np.histogram(site_radius, bins=edges, weights=np.maximum(rho, 0) * volume)[0]
    return result


def angular_flow(position, tangential_velocity, mass, criteria) -> dict:
    bins = int(criteria["angular_bins"])
    index = np.floor(np.mod(np.arctan2(position[:, 1], position[:, 0]), 2 * math.pi)
                     * bins / (2 * math.pi)).astype(int)
    counts = np.bincount(index, minlength=bins)
    means = np.full((bins, 3), np.nan)
    coherence = np.full(bins, np.nan)
    for b in range(bins):
        selected = index == b
        if counts[b] < criteria["angular_bin_min_particles"]:
            continue
        vectors, weights = tangential_velocity[selected], mass[selected]
        denominator = np.average(np.linalg.norm(vectors, axis=1), weights=weights)
        if denominator > 0:
            means[b] = np.average(vectors, axis=0, weights=weights)
            coherence[b] = np.linalg.norm(means[b]) / denominator
    return {"particle_counts": counts, "mean_vectors": means, "coherence": coherence,
            "eligible_bins": int(np.isfinite(coherence).sum()),
            "mean_coherence": float(np.nanmean(coherence)) if np.isfinite(coherence).any() else None}


def measure_frame(arrays: dict, cfg: dict, criteria: dict) -> tuple[dict, dict, dict]:
    pos = arrays["pos"].astype(np.float64)
    velocity = arrays["vel"][:, :3].astype(np.float64)
    acceleration = arrays["acc"][:, :3].astype(np.float64)
    mass = pos[:, 3]
    require(bool((mass > 0).all()), "nonpositive particle mass")
    total = mass.sum()
    center = np.average(pos[:, :3], axis=0, weights=mass)
    center_velocity = np.average(velocity, axis=0, weights=mass)
    relative, vrel = pos[:, :3] - center, velocity - center_velocity
    radius = np.linalg.norm(relative, axis=1)
    radial_unit = np.divide(relative, radius[:, None], out=np.zeros_like(relative), where=radius[:, None] > 0)
    vr = np.sum(vrel * radial_unit, axis=1)
    vt = vrel - vr[:, None] * radial_unit
    r10, r50, r90 = radii_at_quantiles(radius, mass)
    eigen = np.maximum(np.linalg.eigvalsh((relative * mass[:, None]).T @ relative / total), 0)
    axis_ratio = math.sqrt(eigen[0] / eigen[-1]) if eigen[-1] > 0 else 0.0
    ext = np.asarray(cfg["extents"], dtype=np.float64)
    window = np.asarray(cfg["window_center"], dtype=np.float64)
    local = pos[:, :3] - window
    outside = np.any((local < -ext) | (local >= ext), axis=1)
    # Native site positions are tile coordinates in [0,2*extent), not normalized positions.
    site_world = arrays["sites"][:, :3].astype(np.float64) - ext + window
    site_radius = np.linalg.norm(site_world - center, axis=1)
    volume = arrays["site_vol"].astype(np.float64)
    require(bool((volume > 0).all()), "nonpositive site volume")
    y, i = (arrays[key].astype(np.float64) for key in FIELD[:2])
    rho, epsilon = y + i, y - PHI * i
    q = rho**2 / (rho**2 + PHI**-2 + epsilon**2)
    q_error = np.abs(arrays["field_q"] - q)
    epsilon_error = np.abs(arrays["site_eps"] - epsilon)
    q_bad = q_error > criteria["q_abs_tolerance"]
    epsilon_bad = epsilon_error > criteria["epsilon_abs_tolerance"] + criteria["epsilon_rel_tolerance"] * np.abs(epsilon)
    deposited = arrays["site_mass"].astype(np.float64)
    require(bool((deposited >= 0).all()), "negative deposited mass")
    source = arrays["tree_sources"].astype(np.float64)
    weights = arrays["tree_weights"].astype(np.float64)
    expected_source = deposited + np.maximum(rho * volume, 0)
    expected_weight = expected_source * (1 + (PHI**6 - 1) * q)
    # Arithmetic roundoff check, not a new science/acceptance threshold.
    roundoff = 64 * np.finfo(np.float32).eps
    source_bad = np.abs(source[:, 3] - expected_source) > roundoff * np.maximum(1, np.abs(expected_source))
    weight_bad = np.abs(weights - expected_weight) > roundoff * np.maximum(1, np.abs(expected_weight))
    source_xyz_error = float(np.max(np.abs(source[:, :3] - site_world)))
    require(source_xyz_error <= roundoff * max(1, float(np.max(ext))), "tree/site source coordinate mismatch")
    require(bool(np.all(source[:, 4] == arrays["site_psi_y"]) and np.all(source[:, 5] == arrays["site_psi_i"])),
            "tree source field is not the observed accepted boundary")
    frame = {"particle_mass": total, "particle_mass_relative_drift": (total - cfg["total_mass"]) / cfg["total_mass"],
             "R10": r10, "R50": r50, "R90": r90, "axis_c_over_a": axis_ratio,
             "inside_R_fraction": mass[radius <= cfg["radius"]].sum() / total,
             "inside_2R_fraction": mass[radius <= 2 * cfg["radius"]].sum() / total,
             "outside_domain_fraction": mass[outside].sum() / total, "com": center, "com_velocity": center_velocity,
             "kinetic_energy": .5 * np.sum(mass[:, None] * velocity**2),
             "kinetic_energy_com": .5 * np.sum(mass[:, None] * vrel**2),
             "instantaneous_force_work": np.sum(mass[:, None] * velocity * acceleration),
             "radial_velocity_mean": np.average(vr, weights=mass),
             "radial_velocity_rms": math.sqrt(np.average(vr**2, weights=mass)),
             "tangential_velocity_rms": math.sqrt(np.average(np.sum(vt**2, axis=1), weights=mass)),
             "angular_momentum": np.sum(mass[:, None] * np.cross(relative, vrel), axis=0),
             "acceleration_max_abs": np.abs(acceleration).max(), "volume_sum": volume.sum(),
             "q_volume_weighted": np.average(q, weights=volume), "epsilon_volume_weighted": np.average(epsilon, weights=volume),
             "positive_field_mass": np.maximum(rho * volume, 0).sum(), "signed_field_mass": np.sum(rho * volume),
             "deposited_particle_mass": deposited.sum(), "tree_source_mass": source[:, 3].sum(),
             "chord_weighted_tree_mass": weights.sum(),
             "q_max_abs_error": q_error.max(), "q_bad_count": q_bad.sum(),
             "epsilon_max_abs_error": epsilon_error.max(), "epsilon_bad_count": epsilon_bad.sum(),
             "source_mass_bad_count": source_bad.sum(), "source_weight_bad_count": weight_bad.sum(),
             "source_mass_max_abs_error": np.abs(source[:, 3] - expected_source).max(),
             "source_weight_max_abs_error": np.abs(weights - expected_weight).max(),
             "source_coordinate_max_abs_error": source_xyz_error, "formula_comparisons": int(q.size)}
    profile = radial_profile(radius, mass, site_radius, volume, q, epsilon, rho, deposited, cfg["radius"])
    angular = angular_flow(relative, vt, mass, criteria)
    return frame, profile, angular


def measure_kick(before: dict, after: dict, cfg: dict) -> dict:
    require(np.array_equal(before["pos"], after["pos"]), "kick changed particle positions or mass")
    for role in FIELD:
        require(np.array_equal(before[role], after[role]), "kick changed field state")
    pos, v0, v1 = (before["pos"].astype(np.float64), before["vel"][:, :3].astype(np.float64),
                    after["vel"][:, :3].astype(np.float64))
    mass = pos[:, 3]
    radial = pos[:, :3] - np.average(pos[:, :3], axis=0, weights=mass)
    direction = radial / np.linalg.norm(radial, axis=1)[:, None]
    speed = cfg["perturb_fraction"] * math.sqrt(PHI**-3 * mass.sum() / cfg["radius"])
    expected = speed * direction
    expected -= np.average(expected, axis=0, weights=mass)
    delta = v1 - v0
    mean = np.average(delta, axis=0, weights=mass)
    error = np.abs(delta - expected).max()
    landed = bool(np.linalg.norm(delta) > 0 and error < 64 * np.finfo(np.float32).eps * max(1, np.abs(v0).max()))
    return {"landed": landed, "nominal_speed": speed, "measured_delta_rms": math.sqrt(np.average(np.sum(delta**2, axis=1), weights=mass)),
            "net_velocity_delta": mean, "max_component_error": error,
            "kick_only_energy": .5 * np.sum(mass[:, None] * delta**2),
            "measured_kinetic_energy_change": .5 * np.sum(mass[:, None] * (v1**2 - v0**2))}


def expected_schedule(cfg: dict) -> list[tuple[int, str]]:
    result = []
    for step in range(0, cfg["target_steps"] + 1, cfg["snapshot_stride"]):
        phase = "initial" if step == 0 else "before_perturbation" if step == cfg["perturb_step"] else "sample"
        result.append((step, phase))
        if step == cfg["perturb_step"]:
            result.append((step, "after_perturbation"))
    return result


def analyze_arm(directory: Path, cfg: dict, criteria: dict, expected_sources: dict) -> dict:
    receipt = read_json(directory / "receipt.json")
    require(receipt["schema"] == "cassi_native_sphere_arm_v1" and receipt["id"] == cfg["id"], "arm identity/schema mismatch")
    require(receipt["config"] == cfg, "receipt config differs from frozen spec")
    require(receipt["source_hashes"] == expected_sources, "receipt source closure differs from campaign")
    ns = 2 * cfg["site_lattice_n1"]**3
    runtime = receipt["runtime_configuration"]
    for key, expected in {"gridless_physics": True, "physical_matter_active": False,
            "physical_radiation_active": False, "particle_merge": False, "black_holes_enabled": False,
            "freeze_field": cfg["freeze_field"], "site_count": ns, "particle_count": cfg["particle_count"],
            "extents": cfg["extents"], "grid_N": cfg["grid_N"], "tree_cadence": 1,
            "accepted_steps_per_request": 1, "boxless_field": True, "geometry_mode": cfg["geometry_mode"]}.items():
        require(runtime.get(key) == expected, f"runtime {key} differs from registration")
    snapshots = receipt["snapshots"]
    actual = [(s["step"], s["phase"]) for s in snapshots]
    schedule = expected_schedule(cfg)
    complete = receipt["status"] == "COMPLETE" and receipt["completed_steps"] == cfg["target_steps"]
    require(actual == (schedule if complete else schedule[:len(actual)]), "snapshot schedule differs from registration")
    require(bool(snapshots), "no raw observations")
    reader = BlobReader(directory, cfg["particle_count"], ns, cfg["freeze_field"])
    issues = list(receipt["errors"])
    if not complete:
        issues.append("incomplete arm: " + receipt["status"])
    frames, profiles, angular_frames = [], [], []
    first, initial_hashes, previous_phase, previous_angular, before_kick = None, {}, None, None, None
    frozen_identical, particles_changed, deposit_changed = True, False, False
    changed_roles: set[str] = set()
    maximum_field_delta = {role: 0.0 for role in FIELD}
    phase_eligible, phase_alias, persistence_count, persistence_sum = 0, 0, 0, 0.0
    phase_net = np.zeros(ns)
    continuous_phase = np.ones(ns, dtype=bool)
    phase_frames, kick, csr_checks = [], None, 0
    csr_empty_rows = []
    for s in snapshots:
        step, phase = s["step"], s["phase"]
        code_t = step * cfg["dt"]
        require(abs(s["t"] - code_t) < 1e-8, "step/time mismatch")
        require(s["source_boundary_step"] == step and s["field_operator_samples"] > 0, "source boundary/operator did not fire")
        require(s["observation_refresh"] == "mass_derived_tree_only_no_field_commit_no_particle_drift", "wrong observation operator")
        topo = s["topology_status"]
        require(topo[0] >= 1 and topo[1] > 0 and topo[2] == 0 and topo[3] == ns, "invalid topology status")
        raw_tel = s["accepted_step_raw_telemetry"]
        require(len(raw_tel) == 12, "missing accepted-step native telemetry")
        files = s["files"]
        require(all(key in files for key in REQUIRED), "missing required raw arrays")
        if step in (0, cfg["target_steps"]):
            require(all(key in files for key in ENDPOINT), "missing endpoint operator/CSR arrays")
        arrays = {role: reader.load(role, item) for role, item in files.items()}
        if "offsets" in arrays:
            offsets = arrays["offsets"].astype(np.int64)
            neighbors = arrays["neighbors"]
            require(offsets[0] == 0 and offsets[-1] == topo[1] == len(neighbors), "CSR neighbor count mismatch")
            require(bool(np.all(np.diff(offsets) >= 0) and np.all(neighbors < ns)), "invalid CSR rows")
            csr_empty_rows.append(int(np.count_nonzero(np.diff(offsets) == 0)))
            csr_checks += 1
        if first is None:
            first = arrays
            initial_hashes = {role: files[role]["raw_sha256"] for role in IDENTITY}
            for role in FIELD[:2]:
                values = first[role]
                require(values.min() < values.max() and values.min() >= -.010001 and values.max() <= .010001,
                        "initial field is not the registered independent native noise")
            require(bool(np.all(first["vel"][:, :3] == 0)), "initial particles are not at rest")
            require(bool(np.all(first["site_pi_y"] == 0) and np.all(first["site_pi_i"] == 0)), "initial field momenta are not zero")
            initial_deposit_hash = files["site_mass"]["raw_sha256"]
        require(files["sites"]["raw_sha256"] == initial_hashes["sites"], "fixed geometry changed")
        require(files["site_vol"]["raw_sha256"] == initial_hashes["site_vol"], "fixed cell volumes changed")
        for role in (*FIELD, *DERIVED):
            if files[role]["raw_sha256"] != initial_hashes[role]:
                frozen_identical = False
                if role in FIELD:
                    changed_roles.add(role)
            if role in FIELD:
                maximum_field_delta[role] = max(maximum_field_delta[role], float(np.max(np.abs(arrays[role] - first[role]))))
        particles_changed |= files["pos"]["raw_sha256"] != initial_hashes["pos"]
        deposit_changed |= files["site_mass"]["raw_sha256"] != initial_deposit_hash
        frame, profile, angular = measure_frame(arrays, cfg, criteria)
        frame.update(step=step, t=code_t, raw_t=s["t"], phase=phase,
                     topology_status=topo, field_operator_samples=s["field_operator_samples"],
                     accepted_step_telemetry=s["accepted_step_telemetry"], accepted_step_raw_telemetry=raw_tel)
        if abs(frame["particle_mass_relative_drift"]) > criteria["mass_rel_tolerance"]:
            issues.append(f"particle mass drift at step {step}")
        for key in ("q_bad_count", "epsilon_bad_count", "source_mass_bad_count", "source_weight_bad_count"):
            if frame[key]:
                issues.append(f"{key}={frame[key]} at step {step}")
        if phase == "before_perturbation":
            before_kick = arrays
        if phase == "after_perturbation":
            require(before_kick is not None, "kick has no before frame")
            kick = measure_kick(before_kick, arrays, cfg)
            frames[-1], profiles[-1], angular_frames[-1] = frame, {"t": code_t, **profile}, {"t": code_t, **angular}
            continue  # same field/time: do not count a zero-time phase pair
        frames.append(frame)
        profiles.append({"t": code_t, **profile})
        angular_frames.append({"t": code_t, **angular})
        angles = np.arctan2(arrays["site_psi_i"].astype(float), arrays["site_psi_y"].astype(float))
        valid = np.hypot(arrays["site_psi_y"], arrays["site_psi_i"]) >= criteria["phase_amplitude_floor"]
        continuous_phase &= valid
        phase_row = {"t": code_t, "valid_sites": int(valid.sum()), "eligible_pairs": 0, "alias_risk_pairs": 0}
        if previous_phase is not None:
            old_angles, old_valid = previous_phase
            delta = (angles - old_angles + math.pi) % (2 * math.pi) - math.pi
            eligible = valid & old_valid
            aliased = eligible & (np.abs(delta) >= criteria["phase_alias_increment"])
            continuous_phase &= ~aliased
            phase_net += np.where(eligible, delta, 0)
            phase_eligible += int(eligible.sum())
            phase_alias += int(aliased.sum())
            phase_row.update(eligible_pairs=int(eligible.sum()), alias_risk_pairs=int(aliased.sum()),
                             max_principal_increment=float(np.abs(delta[eligible]).max()) if eligible.any() else None)
        previous_phase = angles, valid
        phase_frames.append(phase_row)
        if previous_angular is not None:
            old, new = previous_angular, angular["mean_vectors"]
            eligible = np.all(np.isfinite(old), axis=1) & np.all(np.isfinite(new), axis=1)
            norm = np.linalg.norm(old, axis=1) * np.linalg.norm(new, axis=1)
            eligible &= norm > 0
            persistence_count += int(eligible.sum())
            persistence_sum += float(np.sum(np.sum(old[eligible] * new[eligible], axis=1) / norm[eligible]))
        previous_angular = angular["mean_vectors"]
    if cfg["freeze_field"] and not frozen_identical:
        issues.append("frozen authoritative field changed")
    if not cfg["freeze_field"] and not changed_roles:
        issues.append("evolving field did not fire")
    if not particles_changed or not deposit_changed:
        issues.append("particle/mass-deposit dynamics did not fire")
    if cfg["perturb_step"] >= 0 and (kick is None or not kick["landed"]):
        issues.append("registered perturbation did not land")
    final = [f for f in frames if f["t"] >= criteria["final_window_start"] - 1e-9]
    require(bool(final) or not complete, "no final-window observations")
    checks, window = {}, {}
    if final:
        r90 = np.array([f["R90"] for f in final])
        window = {"sample_count": len(final), "R50_median": np.median([f["R50"] for f in final]),
                  "R90_min": r90.min(), "R90_max": r90.max(), "R90_breathing_ratio": r90.max() / r90.min(),
                  "inside_2R_fraction_min": min(f["inside_2R_fraction"] for f in final),
                  "outside_domain_fraction_max": max(f["outside_domain_fraction"] for f in final),
                  "axis_c_over_a_min": min(f["axis_c_over_a"] for f in final)}
        checks = {"retained": window["inside_2R_fraction_min"] >= criteria["retained_fraction_min"],
                  "domain": window["outside_domain_fraction_max"] <= criteria["outside_domain_fraction_max"],
                  "resolved": window["R90_min"] >= criteria["r90_softening_min"] * cfg["tree_softening"],
                  "breathing": window["R90_breathing_ratio"] <= criteria["r90_breathing_ratio_max"],
                  "spherical": window["axis_c_over_a_min"] >= criteria["axis_ratio_min"]}
    valid_arm = not issues
    bounded = "INCONCLUSIVE" if not valid_arm or not checks.get("resolved", False) else "SUPPORTS" if all(checks.values()) else "CONTRADICTS"
    initial_ranges = {role: {"min": first[role].min(), "max": first[role].max(), "unique": np.unique(first[role]).size} for role in FIELD[:2]}
    return json_value({"id": cfg["id"], "config": cfg, "status": "VALID" if valid_arm else "INCONCLUSIVE",
        "issues": issues, "receipt_sha256": file_sha(directory / "receipt.json"), "receipt_status": receipt["status"],
        "runtime_configuration": runtime, "runtime_seconds": receipt["runtime_seconds"],
        "completed_steps": receipt["completed_steps"], "snapshot_count": len(snapshots),
        "initial_hashes": initial_hashes, "initial_field_ranges": initial_ranges,
        "firing": {"particles_changed": particles_changed, "deposit_changed": deposit_changed,
                   "field_changed_roles": sorted(changed_roles), "frozen_field_byte_identical": frozen_identical,
                   "max_field_delta": maximum_field_delta},
        "integrity": {"blob_declarations": reader.declarations, "unique_blobs_hashed": len(reader.verified_files),
                      "decoded_elements": reader.decoded_elements, "CSR_checks": csr_checks,
                      "CSR_empty_rows_at_endpoints": csr_empty_rows,
                      "formula_site_comparisons": ns * len(snapshots), "source_site_comparisons": ns * len(snapshots)},
        "final_window": window, "bounded_checks": checks, "bounded_sphere": bounded, "kick": kick,
        "phase": {"eligible_pairs": phase_eligible, "alias_risk_pairs": phase_alias,
                  "continuous_nonaliased_sites": int(continuous_phase.sum()), "total_sites": ns,
                  "unwrapped_change_volume_mean": float(np.average(phase_net, weights=arrays["site_vol"])) if phase_alias == 0 and continuous_phase.all() else None,
                  "interpretation": "Phase accumulation unavailable if amplitude gaps or alias risk occur; principal increments are diagnostic, not winding.",
                  "frames": phase_frames},
        "angular_flow": {"adjacent_valid_bin_pairs": persistence_count,
                         "mean_adjacent_direction_cosine": persistence_sum / persistence_count if persistence_count else None,
                         "frames": angular_frames}, "frames": frames, "profiles": profiles})


def final_r50(summary: dict, criteria: dict) -> np.ndarray:
    return np.array([f["R50"] for f in summary["frames"] if f["t"] >= criteria["final_window_start"] - 1e-9])


def pair_identity(left: dict, right: dict) -> dict:
    return {role: left["initial_hashes"][role] == right["initial_hashes"][role] for role in IDENTITY}


def compare_arms(arms: dict, spec: dict) -> dict:
    c = spec["criteria"]
    comparisons, refinements, recoveries, ablations = [], [], [], []
    for arm in spec["arms"]:
        current = arms[arm["id"]]
        if "control_id" not in arm:
            continue
        control = arms[arm["control_id"]]
        identity = pair_identity(current, control)
        # Particle count/site geometry intentionally differ in their resolution arms.
        if arm["family"] not in ("particles_double", "sites_coarse"):
            require(all(identity[role] for role in MATCHED_INITIAL), f"initial particle/field mismatch: {arm['id']}")
        delta = (current["final_window"]["R50_median"] - control["final_window"]["R50_median"]) / arm["radius"]
        row = {"id": arm["id"], "control_id": arm["control_id"], "family": arm["family"],
               "R50_median_difference_over_R": delta, "initial_identity": identity}
        if arm["family"] in ("dt_half", "particles_double", "sites_coarse"):
            row["within_registered_limit"] = abs(delta) <= c["refinement_r50_difference_max"]
            refinements.append(row)
        elif arm["family"] == "perturbation":
            row["kick"] = current["kick"]
            row["recovery"] = "INCONCLUSIVE" if current["status"] != "VALID" else (
                "SUPPORTS" if abs(delta) <= c["recovery_r50_difference_max"] and current["bounded_sphere"] == "SUPPORTS" and current["kick"]["landed"] else "CONTRADICTS")
            recoveries.append(row)
        elif arm["family"] in ("no_mass_source", "no_conversion"):
            row["positive_field_mass_final"] = current["frames"][-1]["positive_field_mass"]
            ablations.append(row)
    base = arms["r9_dynamic_s20260915"]
    repeat = arms["r9_dynamic_s20260915_repeat"]
    repeat_identity = pair_identity(base, repeat)
    require(all(repeat_identity[role] for role in MATCHED_INITIAL), "exact-repeat initial particle/field mismatch")
    repeat_effect = float(np.median(final_r50(repeat, c) - final_r50(base, c)) / 9)
    noise = abs(repeat_effect)
    for radius in (12, 9, 6):
        effects, pairs = [], []
        for seed in (20260915, 20260916):
            dynamic, frozen = arms[f"r{radius}_dynamic_s{seed}"], arms[f"r{radius}_frozen_s{seed}"]
            identity = pair_identity(dynamic, frozen)
            require(all(identity[role] for role in MATCHED_INITIAL), f"dynamic/frozen initial particle/field mismatch R={radius}, seed={seed}")
            effect = float(np.median(final_r50(dynamic, c) - final_r50(frozen, c)) / radius)
            effects.append(effect)
            pairs.append({"seed": seed, "effect_over_R": effect, "initial_identity": identity})
        supported = effects[0] * effects[1] > 0 and min(map(abs, effects)) >= c["field_concentration_effect_min"] and abs(effects[0]) > 3 * noise
        valid = all(arms[f"r{radius}_{mode}_s{seed}"]["status"] == "VALID" for seed in (20260915, 20260916) for mode in ("dynamic", "frozen"))
        verdict = "INCONCLUSIVE" if not valid or noise > c["repeat_discrepancy_max"] else "SUPPORTS" if supported else "CONTRADICTS"
        comparisons.append({"radius": radius, "pairs": pairs, "field_contribution": verdict,
                            "direction": "larger_half_mass_radius" if all(x > 0 for x in effects) else "smaller_half_mass_radius" if all(x < 0 for x in effects) else "seed_dependent"})
    return {"field_contribution": comparisons, "exact_repeat": {"effect_over_R": repeat_effect, "noise_over_R": noise,
            "initial_identity": repeat_identity},
            "refinements": refinements,
            "R9_resolution_robust": all(r["within_registered_limit"] for r in refinements),
            "recovery": recoveries, "ablations": ablations}


def analyze(directory: Path) -> dict:
    manifest = read_json(directory / "campaign.json")
    spec = read_json(directory / "spec.json")
    require(manifest["schema"] == "cassi_native_sphere_campaign_v1" and spec == manifest["spec"], "campaign/spec mismatch")
    planned = {arm["id"] for arm in spec["arms"]}
    runs = {run["id"]: run for run in manifest["runs"]}
    require(set(runs) == planned and len(runs) == len(manifest["runs"]), "campaign run coverage/duplicates")
    hashes = manifest["source_hashes"]
    for name, digest in hashes.items():
        path = Path(next(iter(runs.values()))["command"][0]) if name == "godot_executable" else ROOT / name
        require(file_sha(path) == digest, f"source SHA256 changed: {name}")
    require(file_sha(directory / "preregistration.md") == hashes["research/stellar_cells/native_sphere_prereg.md"], "preregistration copy mismatch")
    require(read_json(ROOT / "research/stellar_cells/native_sphere_spec.json") == spec, "frozen spec differs from source")
    canonical = (ROOT / "scripts/cassi_physics_engine.gd").read_text(encoding="utf-8")
    arms = {}
    for arm in spec["arms"]:
        cfg, run = {**spec["defaults"], **arm}, runs[arm["id"]]
        require(run["returncode"] == 0 and not run["watchdog_timeout"] and run["source_closure_unchanged"], f"unsuccessful execution {arm['id']}")
        variant = run["variant"]
        path = ROOT / variant["path"]
        require(file_sha(path) == variant["variant_sha256"], "engine variant hash mismatch")
        restored = path.read_text(encoding="utf-8")
        for change in reversed(variant["changes"]):
            require(restored.count(change["after"]) == 1, "variant reverse anchor mismatch")
            restored = restored.replace(change["after"], change["before"], 1)
        require(restored == canonical, "variant changes exceed their source-bound substitutions")
        print("ANALYZE " + arm["id"], flush=True)
        expected_sources = {**hashes, "engine_variant": variant["variant_sha256"]}
        arms[arm["id"]] = analyze_arm(directory / arm["id"], cfg, spec["criteria"], expected_sources)
    comparisons = compare_arms(arms, spec)
    return {"schema": "cassi_native_sphere_analysis_v2", "status": "VALID" if all(a["status"] == "VALID" for a in arms.values()) else "INCONCLUSIVE",
            "campaign_root": str(directory), "campaign_manifest_sha256": file_sha(directory / "campaign.json"),
            "spec_sha256": file_sha(directory / "spec.json"), "analyzer_sha256": file_sha(Path(__file__)),
            "source_hashes": hashes, "arm_count": len(arms), "criteria": spec["criteria"],
            "total_steps": sum(a["completed_steps"] for a in arms.values()),
            "total_snapshots": sum(a["snapshot_count"] for a in arms.values()),
            "total_runtime_seconds": sum(a["runtime_seconds"] for a in arms.values()),
            "arms": arms, "comparisons": comparisons,
            "initial_pairing_contract": {"required_byte_identity": list(MATCHED_INITIAL),
                "diagnostic_only_between_launches": ["acc", "sites", "site_vol"],
                "geometry_scope": "Geometry/volumes are byte-fixed within each arm. Independently initialized GPU meshes need not be byte-identical across launches; their variation is retained, not overwritten."},
            "interpretation": "Code-unit fixed-geometry native field/particle experiment. Particle mass, deposited mass, positive field mass and chord-weighted source mass are distinct. No thermodynamic, nuclear, solar or conserved total energy claim."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.campaign_root)
        for arm_id, summary in result["arms"].items():
            save_json(args.campaign_root / arm_id / "summary.json", {k: v for k, v in summary.items() if k != "profiles"})
            save_json(args.campaign_root / arm_id / "profiles.json", {"id": arm_id, "profiles": summary["profiles"]})
        save_json(args.campaign_root / "analysis.json", result)
    except (IntegrityError, OSError, ValueError, KeyError) as exc:
        print("INTEGRITY_FAILURE: " + str(exc), file=sys.stderr)
        return 2
    print(f"MEASURED {result['arm_count']} arms, {result['total_steps']} steps, {result['total_snapshots']} snapshots; integrity={result['status']}")
    return 0 if result["status"] == "VALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
