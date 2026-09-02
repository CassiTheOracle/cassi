#!/usr/bin/env python
"""One-run diagnostic for site interpolation and particle self-exclusion."""

import base64
import hashlib
import json
import sys

import numpy as np

def _f32(encoded: str, count: int, width: int) -> np.ndarray:
    values = np.frombuffer(base64.b64decode(encoded), dtype=np.float32)
    expected = count * width
    if values.size < expected:
        raise ValueError(f"float buffer has {values.size} values; expected {expected}")
    return values[:expected].astype(np.float64)


def _nearest(query: np.ndarray, sites: np.ndarray, k: int,
             chunk: int = 128) -> np.ndarray:
    result = np.empty((query.shape[0], k), dtype=np.int64)
    for start in range(0, query.shape[0], chunk):
        stop = min(start + chunk, query.shape[0])
        delta = query[start:stop, None, :] - sites[None, :, :]
        distance2 = np.einsum("qsi,qsi->qs", delta, delta)
        for row_i, row in enumerate(distance2):
            threshold = np.partition(row, k - 1)[k - 1]
            below = np.flatnonzero(row < threshold)
            tied = np.flatnonzero(row == threshold)
            chosen = np.concatenate((below, tied))
            chosen = chosen[np.lexsort((chosen, row[chosen]))]
            result[start + row_i] = chosen[:k]
    return result


def _relative(sampled: np.ndarray,
              reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    magnitude = np.linalg.norm(reference, axis=1)
    keep = magnitude > 1e-8
    relative = np.linalg.norm(sampled - reference, axis=1) / np.maximum(
        magnitude, 1e-8)
    return relative, keep


def _quartiles(metric: np.ndarray, relative: np.ndarray,
               keep: np.ndarray) -> list[dict]:
    edges = np.quantile(metric[keep], (0.0, 0.25, 0.5, 0.75, 1.0))
    rows = []
    for index in range(4):
        selected = keep & (metric >= edges[index])
        selected &= (
            metric <= edges[index + 1]
            if index == 3 else metric < edges[index + 1]
        )
        values = relative[selected]
        rows.append({
            "lo": float(edges[index]),
            "hi": float(edges[index + 1]),
            "count": int(values.size),
            "median": float(np.median(values)),
            "p99": float(np.percentile(values, 99)),
        })
    return rows


def _i32(encoded: str, count: int, width: int = 1) -> np.ndarray:
    values = np.frombuffer(base64.b64decode(encoded), dtype=np.int32)
    expected = count * width
    if values.size < expected:
        raise ValueError(f"int buffer has {values.size} values; expected {expected}")
    return values[:expected]


def _metrics(sampled: np.ndarray, reference: np.ndarray) -> tuple[dict, np.ndarray, np.ndarray]:
    rel, keep = _relative(sampled, reference)
    dots = np.einsum("ij,ij->i", sampled[keep], reference[keep])
    result = {
        "finite": bool(np.isfinite(sampled).all()),
        "median": float(np.median(rel[keep])),
        "p99": float(np.percentile(rel[keep], 99)),
        "opposite_fraction": float(np.mean(dots < 0.0)),
        "excluded": int((~keep).sum()),
    }
    return result, rel, keep


def _boundary_margin(particles: np.ndarray, sites: np.ndarray,
                     owner: np.ndarray, chunk: int = 64) -> np.ndarray:
    margin = np.empty(particles.shape[0], dtype=np.float64)
    for start in range(0, particles.shape[0], chunk):
        stop = min(start + chunk, particles.shape[0])
        p = particles[start:stop]
        owner_ids = owner[start:stop]
        owner_sites = sites[owner_ids]
        particle_delta = p[:, None, :] - sites[None, :, :]
        particle_d2 = np.einsum("nsi,nsi->ns", particle_delta, particle_delta)
        owner_d2 = np.einsum("ni,ni->n", p - owner_sites, p - owner_sites)
        site_delta = sites[None, :, :] - owner_sites[:, None, :]
        site_distance = np.linalg.norm(site_delta, axis=2)
        candidate = (particle_d2 - owner_d2[:, None]) / np.maximum(
            2.0 * site_distance, 1e-30)
        candidate[np.arange(stop - start), owner_ids] = np.inf
        margin[start:stop] = np.min(candidate, axis=1)
    return margin


def _affine16(particles: np.ndarray, sites: np.ndarray,
              site_gradient: np.ndarray, neighbors: np.ndarray) -> np.ndarray:
    sampled = np.empty_like(particles)
    for particle_i, ids in enumerate(neighbors):
        center = sites[ids[0]]
        design = np.column_stack((
            np.ones(ids.size, dtype=np.float64),
            sites[ids] - center,
        ))
        coefficient, _, _, _ = np.linalg.lstsq(
            design, site_gradient[ids], rcond=None)
        row = np.concatenate(([1.0], particles[particle_i] - center))
        sampled[particle_i] = row @ coefficient
    return sampled


def _mean_accepted_depth(particles: np.ndarray, ncf: np.ndarray,
                         nw: np.ndarray, nr: np.ndarray,
                         theta: float) -> tuple[np.ndarray, np.ndarray]:
    root_half = float(ncf[0, 3])
    mean_depth = np.empty(particles.shape[0], dtype=np.float64)
    accepted_count = np.empty(particles.shape[0], dtype=np.int32)
    for particle_i, target in enumerate(particles):
        stack = [0]
        count = 0
        depth_sum = 0
        while stack:
            node = stack.pop()
            child_base = int(nr[node, 2])
            child_count = int(nr[node, 3])
            half = float(ncf[node, 3])
            delta = target - nw[node, 1:4]
            separation = float(np.linalg.norm(delta))
            contains = bool(np.all(np.abs(delta) <= half))
            opened = child_count > 0 and (
                half / max(separation, 1e-30) > theta or contains)
            if opened:
                for child in range(child_count):
                    child_id = child_base + child
                    if child_id < 0 or child_id >= ncf.shape[0]:
                        raise ValueError(f"invalid child node {child_id}")
                    stack.append(child_id)
            else:
                count += 1
                depth_sum += int(np.rint(np.log2(root_half / half)))
        accepted_count[particle_i] = count
        mean_depth[particle_i] = depth_sum / count if count else np.nan
    return mean_depth, accepted_count


def _monotonic(values: list[float], increasing: bool) -> bool:
    pairs = zip(values, values[1:])
    return all(a <= b for a, b in pairs) if increasing else all(a >= b for a, b in pairs)


def main() -> None:
    input_path = (
        sys.argv[1] if len(sys.argv) > 1
        else "_diag/gravity_interpolation_diagnostic_gpu.json"
    )
    output_path = (
        sys.argv[2] if len(sys.argv) > 2
        else "_diag/gravity_interpolation_diagnostic_result.json"
    )
    raw = open(input_path, "rb").read()
    input_sha256 = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)

    particle_count = int(data["Np"])
    source_count = int(data["nsrc"])
    node_count = int(data["node_count"])
    particles = _f32(data["pos_b64"], particle_count, 4).reshape(-1, 4)[:, :3]
    sites = _f32(data["sites_b64"], source_count, 4).reshape(-1, 4)[:, :3]
    legacy = _f32(data["legacy_grad_b64"], particle_count, 4).reshape(-1, 4)[:, :3]
    corrected = _f32(data["corrected_grad_b64"], particle_count, 4).reshape(-1, 4)[:, :3]
    site_gradient = _f32(data["site_grad_b64"], source_count, 4).reshape(-1, 4)[:, :3]
    legacy_count = _i32(data["legacy_icount_b64"], particle_count)
    corrected_count = _i32(data["corrected_icount_b64"], particle_count)
    ncf = _f32(data["ncf_b64"], node_count, 4).reshape(-1, 4)
    nw = _f32(data["nw_b64"], node_count, 4).reshape(-1, 4)
    nr = _i32(data["nr_b64"], node_count, 4).reshape(-1, 4)
    _i32(data["srcorder_b64"], source_count)

    if not all(np.isfinite(array).all() for array in (
            particles, sites, legacy, corrected, site_gradient, ncf, nw)):
        raise ValueError("diagnostic receipt contains non-finite values")

    legacy_rel, legacy_keep = _relative(legacy, corrected)
    count_difference = legacy_count - corrected_count
    legacy_dots = np.einsum("ij,ij->i", legacy[legacy_keep], corrected[legacy_keep])
    legacy_result = {
        "median": float(np.median(legacy_rel[legacy_keep])),
        "p99": float(np.percentile(legacy_rel[legacy_keep], 99)),
        "maximum": float(np.max(legacy_rel[legacy_keep])),
        "opposite_fraction": float(np.mean(legacy_dots < 0.0)),
        "bit_different_fraction": float(np.mean(np.any(legacy != corrected, axis=1))),
        "interaction_difference_fraction": float(np.mean(count_difference != 0)),
        "interaction_difference_max_abs": int(np.max(np.abs(count_difference))),
    }
    legacy_safe = (
        legacy_result["median"] <= 1e-6
        and legacy_result["p99"] <= 1e-5
        and legacy_result["maximum"] <= 1e-4
        and legacy_result["opposite_fraction"] == 0.0
        and legacy_result["interaction_difference_fraction"] == 0.0
    )
    legacy_result["verdict"] = "LEGACY-SAFE" if legacy_safe else "LEGACY-BIASED"

    neighbors = _nearest(particles, sites, 16)
    owner = neighbors[:, 0]
    nearest = site_gradient[owner]
    delta = particles[:, None, :] - sites[neighbors]
    distance = np.linalg.norm(delta, axis=2)
    weights = 1.0 / np.maximum(distance, 1e-12)
    weights /= np.sum(weights, axis=1, keepdims=True)
    idw16 = np.einsum("nk,nki->ni", weights, site_gradient[neighbors])
    affine = _affine16(particles, sites, site_gradient, neighbors)

    boundary_margin = _boundary_margin(particles, sites, owner)
    mean_depth, replay_count = _mean_accepted_depth(
        particles, ncf, nw, nr, float(data["theta"]))
    replay_difference = replay_count - corrected_count
    depth_valid = bool(np.array_equal(replay_count, corrected_count))

    reconstructions = {}
    affine_boundary: list[dict] = []
    affine_depth: list[dict] | None = None
    for label, sampled in (("nearest", nearest), ("idw16", idw16), ("affine16", affine)):
        metrics, relative, keep = _metrics(sampled, corrected)
        metrics["boundary_margin_quartiles"] = _quartiles(
            boundary_margin, relative, keep)
        metrics["mean_accepted_depth_quartiles"] = (
            _quartiles(mean_depth, relative, keep) if depth_valid else None)
        reconstructions[label] = metrics
        if label == "affine16":
            affine_boundary = metrics["boundary_margin_quartiles"]
            affine_depth = metrics["mean_accepted_depth_quartiles"]
    if not affine_boundary:
        raise ValueError("affine reconstruction was not evaluated")

    boundary_medians = [row["median"] for row in affine_boundary]
    boundary_ratio = boundary_medians[0] / max(boundary_medians[-1], 1e-30)
    boundary_dominated = _monotonic(boundary_medians, increasing=False) and boundary_ratio >= 2.0
    depth_dominated = False
    depth_ratio = None
    if depth_valid:
        if affine_depth is None:
            raise ValueError("affine depth strata were not evaluated")
        depth_medians = [row["median"] for row in affine_depth]
        depth_ratio = depth_medians[-1] / max(depth_medians[0], 1e-30)
        depth_dominated = _monotonic(depth_medians, increasing=True) and depth_ratio >= 2.0

    if boundary_dominated and depth_dominated:
        mechanism = "MIXED: BOUNDARY + DEPTH"
    elif boundary_dominated:
        mechanism = "BOUNDARY-DOMINATED"
    elif depth_dominated:
        mechanism = "DEPTH-DOMINATED"
    else:
        mechanism = "UNRESOLVED"

    receipt = {
        "input_sha256": input_sha256,
        "particle_count": particle_count,
        "source_count": source_count,
        "node_count": node_count,
        "legacy_exclusion": legacy_result,
        "depth_replay": {
            "valid": depth_valid,
            "mismatch_count": int(np.count_nonzero(replay_difference)),
            "max_abs_count_difference": int(np.max(np.abs(replay_difference))),
            "mean_depth_min": float(np.min(mean_depth)),
            "mean_depth_max": float(np.max(mean_depth)),
        },
        "reconstructions": reconstructions,
        "boundary_ratio": float(boundary_ratio),
        "depth_ratio": float(depth_ratio) if depth_ratio is not None else None,
        "mechanism_verdict": mechanism,
    }
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")

    print(f"diagnostic input SHA-256: {input_sha256}")
    print("legacy exclusion: %s med=%.6g p99=%.6g max=%.6g bit-different=%.3f"
          % (legacy_result["verdict"], legacy_result["median"],
             legacy_result["p99"], legacy_result["maximum"],
             legacy_result["bit_different_fraction"]))
    print("depth replay: %s mismatches=%d max-count-difference=%d"
          % ("PASS" if depth_valid else "INCONCLUSIVE",
             receipt["depth_replay"]["mismatch_count"],
             receipt["depth_replay"]["max_abs_count_difference"]))
    for label, metrics in reconstructions.items():
        print("%s: med=%.6g p99=%.6g opposite=%.6g"
              % (label, metrics["median"], metrics["p99"],
                 metrics["opposite_fraction"]))
    print("mechanism: %s boundary-ratio=%.6g depth-ratio=%s"
          % (mechanism, boundary_ratio,
             "INCONCLUSIVE" if depth_ratio is None else f"{depth_ratio:.6g}"))


if __name__ == "__main__":
    main()
