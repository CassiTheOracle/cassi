#!/usr/bin/env python
"""G73/G74: fixed-near-field plus Cartesian harmonic local expansion."""

import base64
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.meshless.stage5_fmm import BHOctree  # pyright: ignore[reportMissingImports]



EXPECTED_SHA256 = "97baf4808cd9a0e889fb65fbd98ce9ef997bd57f38d5d12a792bcbd83ecefafc"
NEAR_COUNT = 256
FIT_COUNT = 48
MAX_ORDER = 5

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


def _source_state(data: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = int(data["nsrc"])
    grid_n = int(data["N"])
    sites = _f32(data["sites_b64"], count, 4).reshape(-1, 4)[:, :3]
    ey = _f32(data["ey_b64"], count, 1)
    ei = _f32(data["ei_b64"], count, 1)
    volume = _f32(data["vol_b64"], count, 1)
    rho_mass = _f32(data["rho_b64"], grid_n ** 3, 1).reshape(
        grid_n, grid_n, grid_n)
    extent = np.array([
        data["extent_x"], data["extent_y"], data["extent_z"]
    ], dtype=np.float64)
    spacing = 2.0 * extent / grid_n
    cell = np.clip(np.floor(sites / spacing).astype(np.int64), 0, grid_n - 1)
    rho_at_site = rho_mass[cell[:, 0], cell[:, 1], cell[:, 2]]

    rho_field = ey + ei
    safe_volume = np.maximum(volume, 1e-12)
    field_mass = np.maximum(
        rho_field * safe_volume, float(data["field_floor"]) * safe_volume)
    mass = rho_at_site * safe_volume + field_mass
    phi = float(data["phi"])
    epsilon = ey - phi * ei
    coherence = rho_field ** 2 / (
        rho_field ** 2 + phi ** -2 + epsilon ** 2)
    weight = mass * (1.0 + (float(data["xi"]) - 1.0) * coherence)
    return sites, weight, np.column_stack((coherence, mass))


def _direct_force(targets: np.ndarray, sites: np.ndarray,
                  weight: np.ndarray, source_ids: np.ndarray,
                  eps2: float) -> np.ndarray:
    source_position = sites[source_ids]
    source_weight = weight[source_ids]
    delta = source_position[None, :, :] - targets[:, None, :]
    distance2 = np.einsum("nsi,nsi->ns", delta, delta)
    softened = distance2 + eps2 + np.maximum(source_weight, 0.0) ** (2.0 / 3.0)
    inverse_r3 = softened ** -1.5
    return np.einsum("s,nsi,ns->ni", source_weight, delta, inverse_r3)


def _monomial_exponents(degree: int) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (x, y, degree - x - y)
        for x in range(degree, -1, -1)
        for y in range(degree - x, -1, -1)
    )


@lru_cache(maxsize=None)
def _harmonic_nullspace(degree: int) -> tuple[tuple[tuple[int, int, int], ...], np.ndarray]:
    exponents = _monomial_exponents(degree)
    if degree < 2:
        return exponents, np.eye(len(exponents), dtype=np.float64)

    reduced = _monomial_exponents(degree - 2)
    reduced_index = {exponent: index for index, exponent in enumerate(reduced)}
    laplacian = np.zeros((len(reduced), len(exponents)), dtype=np.float64)
    for column, exponent in enumerate(exponents):
        for axis in range(3):
            power = exponent[axis]
            if power < 2:
                continue
            target = list(exponent)
            target[axis] -= 2
            reduced_exponent = (target[0], target[1], target[2])
            laplacian[reduced_index[reduced_exponent], column] += power * (power - 1)

    _, singular, vh = np.linalg.svd(laplacian, full_matrices=True)
    tolerance = np.finfo(np.float64).eps * max(laplacian.shape) * singular[0]
    rank = int(np.count_nonzero(singular > tolerance))
    nullspace = vh[rank:].T
    expected = 2 * degree + 1
    if nullspace.shape[1] != expected:
        raise ValueError(
            f"degree {degree} harmonic dimension {nullspace.shape[1]} != {expected}")
    return exponents, nullspace


def _monomial_gradients(points: np.ndarray,
                        exponents: tuple[tuple[int, int, int], ...]) -> np.ndarray:
    result = np.zeros((points.shape[0], 3, len(exponents)), dtype=np.float64)
    for column, exponent in enumerate(exponents):
        for axis in range(3):
            if exponent[axis] == 0:
                continue
            value = np.full(points.shape[0], exponent[axis], dtype=np.float64)
            for coordinate in range(3):
                power = exponent[coordinate] - (1 if coordinate == axis else 0)
                if power:
                    value *= points[:, coordinate] ** power
            result[:, axis, column] = value
    return result


def _harmonic_gradients(points: np.ndarray, order: int) -> np.ndarray:
    blocks = []
    for degree in range(1, order + 1):
        exponents, nullspace = _harmonic_nullspace(degree)
        monomial = _monomial_gradients(points, exponents)
        blocks.append(np.einsum("ndm,mk->ndk", monomial, nullspace))
    return np.concatenate(blocks, axis=2)


def _metrics(sampled: np.ndarray, reference: np.ndarray,
             q_owner: np.ndarray, mass_owner: np.ndarray) -> dict:
    relative, keep = _relative(sampled, reference)
    high_q = keep & (q_owner >= np.percentile(q_owner, 75))
    high_mass = keep & (mass_owner >= np.percentile(mass_owner, 75))
    dot = np.einsum("ij,ij->i", sampled[keep], reference[keep])
    result = {
        "finite": bool(np.isfinite(sampled).all()),
        "median": float(np.median(relative[keep])),
        "p99": float(np.percentile(relative[keep], 99)),
        "high_q_median": float(np.median(relative[high_q])),
        "high_mass_median": float(np.median(relative[high_mass])),
        "opposite_fraction": float(np.mean(dot < 0.0)),
        "excluded": int(np.count_nonzero(~keep)),
    }
    result["g73_pass"] = bool(
        result["finite"]
        and result["median"] <= 1e-2
        and result["p99"] <= 5e-2
        and result["high_q_median"] <= 2e-2
        and result["high_mass_median"] <= 2e-2
        and result["opposite_fraction"] <= 1e-3
    )
    return result


def _kernel_control(particles: np.ndarray, reference: np.ndarray,
                    sites: np.ndarray, weight: np.ndarray,
                    eps2: float) -> dict:
    indices = np.rint(np.linspace(0, particles.shape[0] - 1, 32)).astype(np.int64)
    sampled = _direct_force(
        particles[indices], sites, weight, np.arange(sites.shape[0]), eps2)
    relative, keep = _relative(sampled, reference[indices])
    dot = np.einsum("ij,ij->i", sampled[keep], reference[indices][keep])
    result = {
        "indices": indices.tolist(),
        "finite": bool(np.isfinite(sampled).all()),
        "median": float(np.median(relative[keep])),
        "p99": float(np.percentile(relative[keep], 99)),
        "opposite_fraction": float(np.mean(dot < 0.0)),
    }
    result["pass"] = bool(
        result["finite"]
        and result["median"] <= 1e-3
        and result["p99"] <= 1e-2
        and result["opposite_fraction"] == 0.0
    )
    return result


def _tree_control(particles: np.ndarray, reference: np.ndarray,
                  sites: np.ndarray, mass: np.ndarray, gain: np.ndarray,
                  data: dict) -> dict:
    indices = np.rint(np.linspace(0, particles.shape[0] - 1, 32)).astype(np.int64)
    tree = BHOctree(
        sites,
        mass,
        g=gain,
        leaf_cap=int(data["leaf_cap"]),
        eps2=float(data["eps2"]),
        max_depth=int(data["max_levels"]),
        density_aware=True,
    )
    sampled = tree.force(
        particles[indices],
        theta=float(data["theta"]),
        quad=True,
        exclude_self=False,
    )
    if not isinstance(sampled, np.ndarray):
        raise TypeError("tree force unexpectedly returned a potential tuple")
    relative, keep = _relative(sampled, reference[indices])
    dot = np.einsum("ij,ij->i", sampled[keep], reference[indices][keep])
    result = {
        "indices": indices.tolist(),
        "finite": bool(np.isfinite(sampled).all()),
        "median": float(np.median(relative[keep])),
        "p99": float(np.percentile(relative[keep], 99)),
        "opposite_fraction": float(np.mean(dot < 0.0)),
    }
    result["pass"] = bool(
        result["finite"]
        and result["median"] <= 1e-2
        and result["opposite_fraction"] == 0.0
    )
    return result


def main() -> None:
    tree_control_mode = "--tree-control" in sys.argv[1:]
    paths = [argument for argument in sys.argv[1:] if argument != "--tree-control"]
    input_path = (
        paths[0] if paths
        else "_diag/gravity_interpolation_diagnostic_gpu.json"
    )
    output_path = (
        paths[1] if len(paths) > 1
        else (
            "_diag/gravity_fmm_local_result_v2.json"
            if tree_control_mode
            else "_diag/gravity_fmm_local_result.json"
        )
    )
    gate = "G74" if tree_control_mode else "G73"
    raw = open(input_path, "rb").read()
    input_sha256 = hashlib.sha256(raw).hexdigest()
    if input_sha256 != EXPECTED_SHA256:
        print(
            f"{gate}: INCONCLUSIVE — frozen input mismatch "
            f"(expected {EXPECTED_SHA256}, got {input_sha256})")
        raise SystemExit(2)
    data = json.loads(raw)
    if (
        int(data["leaf_cap"]) != 1
        or int(data["legacy_selector"]) != 1
        or int(data["corrected_selector"]) != 2
    ):
        print(f"{gate}: INCONCLUSIVE — receipt contract mismatch")
        raise SystemExit(2)

    particle_count = int(data["Np"])
    source_count = int(data["nsrc"])
    particles = _f32(data["pos_b64"], particle_count, 4).reshape(-1, 4)[:, :3]
    reference = _f32(
        data["corrected_grad_b64"], particle_count, 4).reshape(-1, 4)[:, :3]
    site_gradient = _f32(
        data["site_grad_b64"], source_count, 4).reshape(-1, 4)[:, :3]
    tree_interactions = np.frombuffer(
        base64.b64decode(data["corrected_icount_b64"]), dtype=np.int32
    )[:particle_count]
    sites, weight, source_strata = _source_state(data)
    if not all(np.isfinite(array).all() for array in (
        particles, reference, site_gradient, sites, weight, source_strata
    )):
        print(f"{gate}: INCONCLUSIVE — non-finite input")
        raise SystemExit(2)

    eps2 = float(data["eps2"])
    if tree_control_mode:
        gain = 1.0 + (float(data["xi"]) - 1.0) * source_strata[:, 0]
        control = _tree_control(
            particles, reference, sites, source_strata[:, 1], gain, data)
        control_kind = "tree"
    else:
        control = _kernel_control(particles, reference, sites, weight, eps2)
        control_kind = "kernel"
    owner = _nearest(particles, sites, 1)[:, 0]
    unique_owner, owner_inverse = np.unique(owner, return_inverse=True)
    neighborhoods = _nearest(sites[unique_owner], sites, NEAR_COUNT + 1, chunk=64)
    predictions = {
        order: np.empty_like(reference) for order in range(1, MAX_ORDER + 1)
    }
    target_ratios = np.empty(particle_count, dtype=np.float64)
    order5_rank = []
    order5_condition = []

    for owner_row, owner_id in enumerate(unique_owner):
        particle_ids = np.flatnonzero(owner_inverse == owner_row)
        neighbor_ids = neighborhoods[owner_row]
        near_ids = neighbor_ids[:NEAR_COUNT]
        fit_ids = neighbor_ids[:FIT_COUNT]
        center = sites[owner_id]
        far_radius = float(np.linalg.norm(sites[neighbor_ids[NEAR_COUNT]] - center))
        if far_radius <= 0.0:
            raise ValueError("non-positive first-excluded far radius")

        target_ratios[particle_ids] = np.linalg.norm(
            particles[particle_ids] - center, axis=1) / far_radius
        near_at_fit = _direct_force(sites[fit_ids], sites, weight, near_ids, eps2)
        far_at_fit = site_gradient[fit_ids] - near_at_fit
        fit_u = (sites[fit_ids] - center) / far_radius
        target_u = (particles[particle_ids] - center) / far_radius
        fit_basis = _harmonic_gradients(fit_u, MAX_ORDER)
        target_basis = _harmonic_gradients(target_u, MAX_ORDER)
        near_at_target = _direct_force(
            particles[particle_ids], sites, weight, near_ids, eps2)

        for order in range(1, MAX_ORDER + 1):
            coefficient_count = order * (order + 2)
            design = fit_basis[:, :, :coefficient_count].reshape(
                FIT_COUNT * 3, coefficient_count)
            coefficient, _, rank, singular = np.linalg.lstsq(
                design, far_at_fit.reshape(-1), rcond=None)
            far_prediction = np.einsum(
                "ndk,k->nd", target_basis[:, :, :coefficient_count], coefficient)
            predictions[order][particle_ids] = near_at_target + far_prediction
            if order == MAX_ORDER:
                order5_rank.append(int(rank))
                condition = (
                    float(singular[0] / singular[-1])
                    if singular.size and singular[-1] > 0.0 else float("inf")
                )
                order5_condition.append(condition)

    q_owner = source_strata[owner, 0]
    mass_owner = source_strata[owner, 1]
    metrics = {
        str(order): _metrics(
            predictions[order], reference, q_owner, mass_owner)
        for order in range(1, MAX_ORDER + 1)
    }
    condition = np.asarray(order5_condition, dtype=np.float64)
    geometry_valid = bool(np.isfinite(target_ratios).all() and target_ratios.max() < 1.0)
    rank_valid = bool(all(rank == MAX_ORDER * (MAX_ORDER + 2) for rank in order5_rank))
    condition_valid = bool(
        np.isfinite(condition).all() and np.percentile(condition, 99) <= 1e10)
    predictions_finite = bool(all(
        np.isfinite(prediction).all() for prediction in predictions.values()))
    controls_valid = bool(
        control["pass"] and geometry_valid and rank_valid
        and condition_valid and predictions_finite)

    p1 = metrics["1"]
    p5 = metrics["5"]
    improvement = bool(
        p5["median"] <= 0.8 * p1["median"]
        and p5["p99"] <= 0.8 * p1["p99"]
    )
    if not controls_valid:
        verdict = "INCONCLUSIVE"
        exit_code = 2
    elif p1["g73_pass"]:
        verdict = "LOW-ORDER FAR FIELD SUFFICIENT"
        exit_code = 0
    elif p5["g73_pass"] and improvement:
        verdict = "SUPPORTS HIGHER-ORDER LOCAL/FMM"
        exit_code = 0
    else:
        verdict = "DOES NOT SUPPORT"
        exit_code = 1

    result = {
        "input_sha256": input_sha256,
        "particle_count": particle_count,
        "source_count": source_count,
        "unique_owner_count": int(unique_owner.size),
        "near_count": NEAR_COUNT,
        "fit_count": FIT_COUNT,
        "orders": list(range(1, MAX_ORDER + 1)),
        "control_kind": control_kind,
        f"{control_kind}_control": control,
        "geometry": {
            "valid": geometry_valid,
            "target_radius_ratio_min": float(np.min(target_ratios)),
            "target_radius_ratio_median": float(np.median(target_ratios)),
            "target_radius_ratio_p99": float(np.percentile(target_ratios, 99)),
            "target_radius_ratio_max": float(np.max(target_ratios)),
        },
        "order5_design": {
            "rank_valid": rank_valid,
            "expected_rank": MAX_ORDER * (MAX_ORDER + 2),
            "condition_valid": condition_valid,
            "condition_median": float(np.median(condition)),
            "condition_p99": float(np.percentile(condition, 99)),
            "condition_max": float(np.max(condition)),
        },
        "metrics": metrics,
        "higher_order_improvement": improvement,
        "work_proxy": {
            "candidate_terms_per_particle": NEAR_COUNT + MAX_ORDER * (MAX_ORDER + 2),
            "tree_interactions_min": int(np.min(tree_interactions)),
            "tree_interactions_median": float(np.median(tree_interactions)),
            "tree_interactions_p99": float(np.percentile(tree_interactions, 99)),
            "tree_interactions_max": int(np.max(tree_interactions)),
        },
        "controls_valid": controls_valid,
        f"{gate.lower()}_pass": bool(controls_valid and p5["g73_pass"]),
        "verdict": verdict,
    }
    with open(output_path, "w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")

    print("=== higher-order local/FMM reconstruction ===")
    print(f"input SHA-256: {input_sha256}")
    print(
        "%s control: %s median=%.6g p99=%.6g opposite=%.6g"
        % (control_kind, "PASS" if control["pass"] else "FAIL",
           control["median"], control["p99"], control["opposite_fraction"]))
    print(
        "geometry: %s target/far-radius median=%.6g p99=%.6g max=%.6g"
        % ("PASS" if geometry_valid else "FAIL", np.median(target_ratios),
           np.percentile(target_ratios, 99), np.max(target_ratios)))
    print(
        "p5 design: rank=%s condition median=%.6g p99=%.6g max=%.6g"
        % ("PASS" if rank_valid else "FAIL", np.median(condition),
           np.percentile(condition, 99), np.max(condition)))
    for order in range(1, MAX_ORDER + 1):
        row = metrics[str(order)]
        print(
            "p%d: median=%.6g p99=%.6g high-q=%.6g high-mass=%.6g "
            "opposite=%.6g fidelity=%s"
            % (order, row["median"], row["p99"], row["high_q_median"],
               row["high_mass_median"], row["opposite_fraction"],
               "PASS" if row["g73_pass"] else "FAIL"))
    print(
        "work proxy: candidate=%d tree median=%.1f p99=%.1f"
        % (result["work_proxy"]["candidate_terms_per_particle"],
           result["work_proxy"]["tree_interactions_median"],
           result["work_proxy"]["tree_interactions_p99"]))
    print(f"{gate}: {'PASS' if result[f'{gate.lower()}_pass'] else 'FAIL'}")
    print(f"verdict: {verdict}")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
