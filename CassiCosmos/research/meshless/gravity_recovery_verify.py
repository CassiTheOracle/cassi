#!/usr/bin/env python
"""G67: frozen owner-site far/near gravity recovery probe."""

import hashlib
import json
import sys

import numpy as np

from stage5b_verify import _f32

KS_H1 = (1, 8, 16, 32, 64)
KS_H2 = (8, 16, 32, 64)
EXPECTED_INPUT_SHA256 = "268900a2c13e5c3165e0f27e2466f5727d54d8d5571fb7cf77a13f1b26045e4d"


def _nearest(query: np.ndarray, sites: np.ndarray, k: int, chunk: int = 128) -> np.ndarray:
    """Distance order with site-index tie breaking, without a full distance cube."""
    out = np.empty((query.shape[0], k), dtype=np.int64)
    for start in range(0, query.shape[0], chunk):
        stop = min(start + chunk, query.shape[0])
        delta = query[start:stop, None, :] - sites[None, :, :]
        d2 = np.einsum("qsi,qsi->qs", delta, delta)
        for row_i, row in enumerate(d2):
            threshold = np.partition(row, k - 1)[k - 1]
            below = np.flatnonzero(row < threshold)
            tied = np.flatnonzero(row == threshold)
            chosen = np.concatenate((below, tied[: k - below.size]))
            chosen = chosen[np.lexsort((chosen, row[chosen]))]
            out[start + row_i] = chosen[:k]
    return out


def _leaf_sum(targets: np.ndarray, ids: np.ndarray, sites: np.ndarray,
              weights: np.ndarray, eps2: float) -> np.ndarray:
    source_pos = sites[ids]
    source_w = weights[ids]
    delta = targets[:, None, :] - source_pos
    radius2 = np.einsum("nki,nki->nk", delta, delta)
    radius2 += eps2 + np.maximum(source_w, 1e-30) ** (2.0 / 3.0)
    inv_r3 = 1.0 / (radius2 * np.sqrt(radius2))
    return np.sum(-source_w[:, :, None] * delta * inv_r3[:, :, None], axis=1)


def _relative(sampled: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    magnitude = np.linalg.norm(reference, axis=1)
    keep = magnitude > 1e-8
    rel = np.linalg.norm(sampled - reference, axis=1) / np.maximum(magnitude, 1e-8)
    return rel, keep


def _quartiles(metric: np.ndarray, rel: np.ndarray, keep: np.ndarray) -> list[dict]:
    valid_metric = metric[keep]
    edges = np.quantile(valid_metric, (0.0, 0.25, 0.5, 0.75, 1.0))
    rows = []
    for index in range(4):
        selected = keep & (metric >= edges[index])
        selected &= metric <= edges[index + 1] if index == 3 else metric < edges[index + 1]
        values = rel[selected]
        rows.append({
            "lo": float(edges[index]),
            "hi": float(edges[index + 1]),
            "count": int(values.size),
            "median": float(np.median(values)) if values.size else float("nan"),
            "p99": float(np.percentile(values, 99)) if values.size else float("nan"),
        })
    return rows


def _evaluate(label: str, sampled: np.ndarray, reference: np.ndarray,
              q_owner: np.ndarray, mass_owner: np.ndarray,
              owner_distance: np.ndarray, local_fraction: np.ndarray) -> dict:
    rel, keep = _relative(sampled, reference)
    med = float(np.median(rel[keep])) if keep.any() else float("nan")
    p99 = float(np.percentile(rel[keep], 99)) if keep.any() else float("nan")
    high_q = keep & (q_owner >= np.percentile(q_owner, 75))
    high_mass = keep & (mass_owner >= np.percentile(mass_owner, 75))
    med_q = float(np.median(rel[high_q])) if high_q.any() else float("nan")
    med_mass = float(np.median(rel[high_mass])) if high_mass.any() else float("nan")
    opposite = float(np.mean(np.einsum(
        "ij,ij->i", sampled[keep], reference[keep]) < 0.0)) if keep.any() else 1.0
    excluded = int((~keep).sum())
    passed = (
        np.isfinite([med, p99, med_q, med_mass, opposite]).all()
        and med <= 1e-2 and p99 <= 5e-2
        and med_q <= 2e-2 and med_mass <= 2e-2
        and opposite <= 1e-3
    )
    result = {
        "label": label,
        "passed": bool(passed and np.isfinite(sampled).all()),
        "finite": bool(np.isfinite(sampled).all()),
        "median": med,
        "p99": p99,
        "high_q_median": med_q,
        "high_mass_median": med_mass,
        "opposite_fraction": opposite,
        "excluded": excluded,
        "owner_distance_quartiles": _quartiles(owner_distance, rel, keep),
        "local_fraction_quartiles": _quartiles(local_fraction, rel, keep),
    }
    print(
        "[%s] %s med=%.6g p99=%.6g high-q=%.6g high-mass=%.6g opposite=%.6g"
        % (label, "PASS" if result["passed"] else "FAIL", med, p99,
           med_q, med_mass, opposite)
    )
    for axis in ("owner_distance_quartiles", "local_fraction_quartiles"):
        print("  %s=%s" % (axis, result[axis]))
    return result


def _affine_far(sample_ids: np.ndarray, local_ids: np.ndarray,
                particle_pos: np.ndarray, sites: np.ndarray,
                site_grad: np.ndarray, weights: np.ndarray,
                eps2: float, chunk: int = 128) -> np.ndarray:
    output = np.empty_like(particle_pos)
    for start in range(0, particle_pos.shape[0], chunk):
        stop = min(start + chunk, particle_pos.shape[0])
        p = particle_pos[start:stop]
        sample = sample_ids[start:stop]
        local = local_ids[start:stop]
        sample_pos = sites[sample]
        source_pos = sites[local]
        source_w = weights[local]
        delta = sample_pos[:, :, None, :] - source_pos[:, None, :, :]
        radius2 = np.einsum("nskd,nskd->nsk", delta, delta)
        radius2 += eps2 + np.maximum(source_w[:, None, :], 1e-30) ** (2.0 / 3.0)
        inv_r3 = 1.0 / (radius2 * np.sqrt(radius2))
        local_at_samples = np.sum(
            -source_w[:, None, :, None] * delta * inv_r3[:, :, :, None], axis=2)
        residual = site_grad[sample] - local_at_samples
        for local_i in range(stop - start):
            center = sites[sample[local_i, 0]]
            design = np.column_stack((
                np.ones(sample.shape[1], dtype=np.float64),
                sample_pos[local_i] - center,
            ))
            coeff, _, _, _ = np.linalg.lstsq(design, residual[local_i], rcond=None)
            row = np.concatenate(([1.0], p[local_i] - center))
            output[start + local_i] = row @ coeff
    return output


def main() -> None:
    input_path = sys.argv[1] if len(sys.argv) > 1 else "_diag/meshless_gravity_gpu.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "_diag/gravity_recovery_cpu.json"
    with open(input_path, "rb") as stream:
        raw = stream.read()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != EXPECTED_INPUT_SHA256:
        print(
            "G67: UNEVALUABLE — frozen input missing "
            f"(expected {EXPECTED_INPUT_SHA256}, got {actual_sha256})"
        )
        raise SystemExit(2)
    data = json.loads(raw)

    particle_count = int(data["Np"])
    source_count = int(data["nsrc"])
    grid_n = int(data["N"])
    phi = float(data["phi"])
    xi = float(data["xi"])
    eps2 = float(data["eps2"])
    extent = np.asarray(
        (data["extent_x"], data["extent_y"], data["extent_z"]), dtype=np.float64)

    sites = _f32(data["sites_b64"], source_count, 4).reshape(source_count, 4)[:, :3]
    ey = _f32(data["ey_b64"], source_count, 1)
    ei = _f32(data["ei_b64"], source_count, 1)
    volume = _f32(data["vol_b64"], source_count, 1)
    density = _f32(data["rho_b64"], grid_n * grid_n * grid_n, 1).reshape(
        grid_n, grid_n, grid_n)
    particle_pos = _f32(data["pos_b64"], particle_count, 4).reshape(
        particle_count, 4)[:, :3]
    reference = _f32(data["grad_b64"], particle_count, 4).reshape(
        particle_count, 4)[:, :3]
    site_grad = _f32(data["site_grad_b64"], source_count, 4).reshape(
        source_count, 4)[:, :3]

    spacing = 2.0 * extent / float(grid_n)
    grid_coord = np.clip(np.floor(sites / spacing).astype(np.int64), 0, grid_n - 1)
    deposited = density[grid_coord[:, 0], grid_coord[:, 1], grid_coord[:, 2]]
    rho_field = ey + ei
    volume_safe = np.maximum(volume, 1e-12)
    mass = deposited * volume_safe + np.maximum(rho_field * volume_safe, 1e-6 * volume_safe)
    epsilon = ey - phi * ei
    coherence = rho_field * rho_field / (
        rho_field * rho_field + phi ** -2 + epsilon * epsilon)
    chord = 1.0 + (xi - 1.0) * coherence
    weight = mass * chord

    print("=== G67: owner-site far/near recovery ===")
    owner = _nearest(particle_pos, sites, 1)[:, 0]
    sample16 = _nearest(particle_pos, sites, 16)
    site_neighbors = _nearest(sites, sites, max(KS_H1))
    owner_distance = np.linalg.norm(particle_pos - sites[owner], axis=1)
    reference_mag = np.maximum(np.linalg.norm(reference, axis=1), 1e-8)
    q_owner = coherence[owner]
    mass_owner = weight[owner]

    h1_results = []
    winner = None
    for k in KS_H1:
        local_ids = site_neighbors[owner, :k]
        local_particle = _leaf_sum(particle_pos, local_ids, sites, weight, eps2)
        local_owner = _leaf_sum(sites[owner], local_ids, sites, weight, eps2)
        sampled = site_grad[owner] + local_particle - local_owner
        result = _evaluate(
            "H1-K%d" % k, sampled, reference, q_owner, mass_owner,
            owner_distance, np.linalg.norm(local_particle, axis=1) / reference_mag)
        result["k"] = k
        h1_results.append(result)
        if winner is None and result["passed"]:
            winner = {"kind": "H1", "k": k}

    h2_results = []
    if winner is None:
        print("=== H1 has no passing K; executing registered H2 fallback ===")
        for k in KS_H2:
            local_ids = site_neighbors[owner, :k]
            local_particle = _leaf_sum(particle_pos, local_ids, sites, weight, eps2)
            far = _affine_far(
                sample16, local_ids, particle_pos, sites, site_grad, weight, eps2)
            sampled = far + local_particle
            result = _evaluate(
                "H2-K%d" % k, sampled, reference, q_owner, mass_owner,
                owner_distance, np.linalg.norm(local_particle, axis=1) / reference_mag)
            result["k"] = k
            h2_results.append(result)
            if winner is None and result["passed"]:
                winner = {"kind": "H2", "k": k}

    receipt = {
        "input_sha256": actual_sha256,
        "particle_count": particle_count,
        "source_count": source_count,
        "h1": h1_results,
        "h2": h2_results,
        "winner": winner,
    }
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("G67: %s%s" % (
        "PASS" if winner is not None else "FAIL",
        " winner=%s" % winner if winner is not None else " — Arm H REJECT",
    ))
    raise SystemExit(0 if winner is not None else 1)


if __name__ == "__main__":
    main()
