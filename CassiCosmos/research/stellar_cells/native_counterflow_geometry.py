"""Pure geometry diagnostics for native wave-energy current channels.

The functions in this module only consume already reconstructed site positions,
volumes and component current vectors.  They do not infer particle velocities or
alter the native current definition.  All geometry thresholds are supplied by
``criteria`` (with the frozen specification values as defaults for convenient
analytic calibration calls).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


# These are the values in native_counterflow_spec.json.  Keeping the defaults
# here makes the pure calibration API usable without a file read; production
# callers pass the frozen ``geometry`` object explicitly.
_DEFAULT_GEOMETRY = {
    "axis_ratio_min": 1.25,
    "slices": 8,
    "minimum_consecutive_slices": 6,
    "site_weight_relative_floor": 1e-8,
    "current_floor": 1e-18,
    "effective_sites_min": 8,
    "slice_width_over_spacing_min": 1,
    "separation_over_spacing_min": 2,
    "separation_over_width_min": 1,
    "winding_turns_min": 0.5,
    "adjacent_angle_abs_max": math.pi / 2.0,
    "winding_fit_r2_min": 0.8,
    "winding_monotonic_fraction_min": 0.8,
    "current_coherence_min": 0.5,
    "tangent_alignment_abs_min": 0.7,
    "counterdirected_slice_fraction_min": 0.75,
}




def _sites(value: Any) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        # ``world_sites`` is deliberately strict.  Tile coordinates with a
        # fourth payload column belong at the caller boundary, where the
        # extents conversion is authoritative.
        raise ValueError("world_sites must have shape (N, 3)")
    if not np.isfinite(array).all():
        raise ValueError("world_sites contains nonfinite values")
    return array


def _vectors(name: str, value: Any, count: int) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape != (count, 3):
        raise ValueError(f"{name} must have shape ({count}, 3)")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains nonfinite values")
    return array


def _vector(value: Optional[np.ndarray]) -> Optional[List[float]]:
    if value is None:
        return None
    return [float(component) for component in np.asarray(value, dtype=np.float64)]


def _scalar(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _criterion(criteria: Optional[dict], key: str) -> float:
    source = _DEFAULT_GEOMETRY if criteria is None else criteria
    value = source.get(key, _DEFAULT_GEOMETRY[key])
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"geometry criterion {key!r} is not numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"geometry criterion {key!r} is nonfinite")
    return result


def _relative_active_weights(
    inside: np.ndarray,
    current_norm: np.ndarray,
    volumes: np.ndarray,
    current_floor: float,
    relative_floor: float,
) -> Tuple[np.ndarray, np.ndarray, Optional[float], Optional[float], int]:
    """Build one component's flux weights and explicit support mask."""
    raw = volumes * current_norm
    inside_raw = raw[inside]
    maximum = float(np.max(inside_raw)) if inside_raw.size else None
    weight_floor = maximum * relative_floor if maximum is not None else None
    if maximum is None or maximum <= 0.0:
        active = np.zeros(inside.shape, dtype=bool)
    else:
        active = inside & (current_norm > current_floor) & (raw >= weight_floor)
    return raw, active, maximum, weight_floor, int(np.count_nonzero(active))


def _weighted_channel_stats(
    relative: np.ndarray,
    axis: np.ndarray,
    origin: np.ndarray,
    current: np.ndarray,
    current_norm: np.ndarray,
    raw_weights: np.ndarray,
    active: np.ndarray,
) -> Dict[str, Any]:
    """Measure one flux-weighted channel in one axial slice."""
    selected = np.flatnonzero(active)
    if selected.size == 0:
        return {
            "site_count": 0,
            "weight_sum": None,
            "centroid": None,
            "width": None,
            "effective_n": None,
            "mean_current": None,
            "mean_current_norm": None,
            "current_coherence": None,
        }

    weights = raw_weights[selected]
    total = float(np.sum(weights))
    squared = float(np.sum(weights * weights))
    if not math.isfinite(total) or total <= 0.0 or squared <= 0.0:
        # This cannot occur for a valid positive-volume input, but retaining a
        # missing result is safer than manufacturing a centroid on bad data.
        return {
            "site_count": int(selected.size),
            "weight_sum": None,
            "centroid": None,
            "width": None,
            "effective_n": None,
            "mean_current": None,
            "mean_current_norm": None,
            "current_coherence": None,
        }

    points = relative[selected]
    centroid_relative = np.sum(points * weights[:, None], axis=0) / total
    centroid = centroid_relative + origin
    axial_offset = np.dot(centroid_relative, axis)
    transverse = points - np.dot(points, axis)[:, None] * axis
    centroid_transverse = centroid_relative - axial_offset * axis
    transverse_delta = transverse - centroid_transverse
    width_sq = float(np.sum(weights * np.sum(transverse_delta * transverse_delta, axis=1)) / total)
    width = math.sqrt(max(width_sq, 0.0))

    mean_current = np.sum(current[selected] * weights[:, None], axis=0) / total
    mean_norm = float(np.linalg.norm(mean_current))
    mean_speed = float(np.sum(weights * current_norm[selected]) / total)
    coherence = mean_norm / mean_speed if mean_speed > 0.0 else None
    effective_n = total * total / squared
    return {
        "site_count": int(selected.size),
        "weight_sum": total,
        "centroid": centroid,
        "width": width,
        "effective_n": effective_n,
        "mean_current": mean_current,
        "mean_current_norm": mean_norm,
        "current_coherence": coherence,
    }


def _unit(value: np.ndarray) -> Optional[np.ndarray]:
    length = float(np.linalg.norm(value))
    return value / length if math.isfinite(length) and length > 0.0 else None


def _canonical_axis(value: np.ndarray) -> Optional[np.ndarray]:
    unit = _unit(value)
    if unit is None:
        return None
    # Eigenvectors have an arbitrary sign.  Lexicographic sign selection makes
    # repeated runs and rotated analytic controls deterministic.
    for component in unit:
        if abs(float(component)) > 1e-15:
            if component < 0.0:
                unit = -unit
            break
    return unit


def _right_handed_frame(axis: Optional[np.ndarray]) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    if axis is None:
        return None, None, None
    # The least-aligned Cartesian reference avoids a small cross product while
    # retaining a deterministic tie break (x, then y, then z).
    reference_index = int(np.argmin(np.abs(axis)))
    reference = np.eye(3, dtype=np.float64)[reference_index]
    transverse_u = _unit(np.cross(axis, reference))
    if transverse_u is None:
        return None, None, None
    transverse_v = _unit(np.cross(axis, transverse_u))
    if transverse_v is None:
        return None, None, None
    # Columns [u, v, axis] have positive determinant by construction.
    return transverse_u, transverse_v, axis


def _longest_true_run(mask: Sequence[bool]) -> Tuple[int, int, int]:
    best_start, best_length = 0, 0
    current_start, current_length = 0, 0
    for index, value in enumerate(mask):
        if bool(value):
            if current_length == 0:
                current_start = index
            current_length += 1
            if current_length > best_length:
                best_start, best_length = current_start, current_length
        else:
            current_length = 0
    end = best_start + best_length - 1 if best_length else None
    return best_start, best_length, end


def _centroid_tangents(
    centroids: Sequence[Optional[np.ndarray]],
    axis: np.ndarray,
    slice_centers: np.ndarray,
) -> List[Optional[np.ndarray]]:
    """Finite-difference tangent of a centroid path, oriented along +axis."""
    valid = np.asarray([centroid is not None for centroid in centroids], dtype=bool)
    result: List[Optional[np.ndarray]] = [None] * len(centroids)
    for index in range(len(centroids)):
        if not valid[index]:
            continue
        derivative = None
        if index > 0 and index + 1 < len(centroids) and valid[index - 1] and valid[index + 1]:
            delta_z = float(slice_centers[index + 1] - slice_centers[index - 1])
            if delta_z > 0.0:
                derivative = (centroids[index + 1] - centroids[index - 1]) / delta_z
        elif index + 1 < len(centroids) and valid[index + 1]:
            delta_z = float(slice_centers[index + 1] - slice_centers[index])
            if delta_z > 0.0:
                derivative = (centroids[index + 1] - centroids[index]) / delta_z
        elif index > 0 and valid[index - 1]:
            delta_z = float(slice_centers[index] - slice_centers[index - 1])
            if delta_z > 0.0:
                derivative = (centroids[index] - centroids[index - 1]) / delta_z
        if derivative is None:
            continue
        tangent = _unit(derivative)
        if tangent is None:
            continue
        if float(np.dot(tangent, axis)) < 0.0:
            tangent = -tangent
        result[index] = tangent
    return result


def _predicate(value: Optional[bool], name: str, reasons: List[str]) -> None:
    if value is False:
        reasons.append(name)


def measure_channels(
    world_sites: Any,
    current_y: Any,
    current_i: Any,
    volumes: Any,
    center: Any,
    radius: float,
    spacing: float,
    criteria: Optional[dict],
) -> Dict[str, Any]:
    """Measure the frozen axis-resolved paired-channel geometry.

    ``world_sites`` are physical site coordinates (tile coordinates must be
    converted by the caller).  ``current_y`` and ``current_i`` are the native
    graph-current vectors, not particle velocities.  The result is JSON-ready:
    vectors are lists, absent quantities are ``None``, and exactly eight slice
    records are always returned.
    """
    sites = _sites(world_sites)
    count = sites.shape[0]
    y_current = _vectors("current_y", current_y, count)
    i_current = _vectors("current_i", current_i, count)
    volume = np.asarray(volumes, dtype=np.float64)
    if volume.ndim != 1 or volume.shape[0] != count:
        raise ValueError(f"volumes must have shape ({count},)")
    if not np.isfinite(volume).all() or np.any(volume <= 0.0):
        raise ValueError("volumes must be finite and positive")
    sphere_center = np.asarray(center, dtype=np.float64)
    if sphere_center.shape != (3,) or not np.isfinite(sphere_center).all():
        raise ValueError("center must have shape (3,)")
    try:
        sphere_radius = float(radius)
        grid_spacing = float(spacing)
    except (TypeError, ValueError) as exc:
        raise ValueError("radius and spacing must be numeric") from exc
    if not math.isfinite(sphere_radius) or sphere_radius <= 0.0:
        raise ValueError("radius must be finite and positive")
    if not math.isfinite(grid_spacing) or grid_spacing <= 0.0:
        raise ValueError("spacing must be finite and positive")

    geometry = _DEFAULT_GEOMETRY if criteria is None else criteria
    slice_count = int(geometry.get("slices", _DEFAULT_GEOMETRY["slices"]))
    if slice_count != 8:
        raise ValueError("native counterflow geometry requires exactly eight slices")
    axis_ratio_min = _criterion(criteria, "axis_ratio_min")
    minimum_run = int(_criterion(criteria, "minimum_consecutive_slices"))
    relative_floor = _criterion(criteria, "site_weight_relative_floor")
    current_floor = _criterion(criteria, "current_floor")
    effective_sites_min = _criterion(criteria, "effective_sites_min")
    width_spacing_min = _criterion(criteria, "slice_width_over_spacing_min")
    separation_spacing_min = _criterion(criteria, "separation_over_spacing_min")
    separation_width_min = _criterion(criteria, "separation_over_width_min")
    winding_turns_min = _criterion(criteria, "winding_turns_min")
    angle_limit = _criterion(criteria, "adjacent_angle_abs_max")
    fit_r2_min = _criterion(criteria, "winding_fit_r2_min")
    monotonic_min = _criterion(criteria, "winding_monotonic_fraction_min")
    coherence_min = _criterion(criteria, "current_coherence_min")
    tangent_min = _criterion(criteria, "tangent_alignment_abs_min")
    counterdirected_min = _criterion(criteria, "counterdirected_slice_fraction_min")
    if relative_floor < 0.0 or current_floor < 0.0 or angle_limit <= 0.0:
        raise ValueError("invalid nonnegative geometry floor or angle criterion")

    relative = sites - sphere_center[None, :]
    distance = np.linalg.norm(relative, axis=1)
    inside = distance <= sphere_radius
    y_norm = np.linalg.norm(y_current, axis=1)
    i_norm = np.linalg.norm(i_current, axis=1)
    y_weight, y_active, y_max, y_weight_floor, y_support = _relative_active_weights(
        inside, y_norm, volume, current_floor, relative_floor
    )
    i_weight, i_active, i_max, i_weight_floor, i_support = _relative_active_weights(
        inside, i_norm, volume, current_floor, relative_floor
    )
    combined_weight = np.where(y_active, y_weight, 0.0) + np.where(i_active, i_weight, 0.0)
    combined_support = combined_weight > 0.0

    eigenvalues: Optional[np.ndarray] = None
    prolate_axis: Optional[np.ndarray] = None
    oblate_axis: Optional[np.ndarray] = None
    prolate_gap: Optional[float] = None
    oblate_gap: Optional[float] = None
    prolate_gap_ratio: Optional[float] = None
    oblate_gap_ratio: Optional[float] = None
    selected_kind: Optional[str] = None
    axis: Optional[np.ndarray] = None
    covariance_center: Optional[np.ndarray] = None
    covariance: Optional[np.ndarray] = None
    if np.any(combined_support):
        points = relative[combined_support]
        weights = combined_weight[combined_support]
        total_weight = float(np.sum(weights))
        if total_weight > 0.0 and math.isfinite(total_weight):
            covariance_center = np.sum(points * weights[:, None], axis=0) / total_weight
            centered = points - covariance_center[None, :]
            covariance = (centered * weights[:, None]).T @ centered / total_weight
            covariance = (covariance + covariance.T) * 0.5
            values, vectors = np.linalg.eigh(covariance)
            values = np.maximum(values, 0.0)
            eigenvalues = values
            prolate_axis = _canonical_axis(vectors[:, 2])
            oblate_axis = _canonical_axis(vectors[:, 0])
            prolate_gap = float(values[2] - values[1])
            oblate_gap = float(values[1] - values[0])
            if values[1] > 0.0:
                prolate_gap_ratio = float(values[2] / values[1])
            if values[0] > 0.0:
                oblate_gap_ratio = float(values[1] / values[0])
            # Select by the larger raw prolate/oblate eigenvalue gap, as
            # frozen by the analysis specification.  The selected adjacent
            # eigenvalue ratio is a separate uniqueness predicate.
            selected_kind = "prolate" if prolate_gap >= oblate_gap else "oblate"
            axis = prolate_axis if selected_kind == "prolate" else oblate_axis

    axis_gap_ratio = prolate_gap_ratio if selected_kind == "prolate" else oblate_gap_ratio
    axis_identifiable = bool(axis is not None and axis_gap_ratio is not None and axis_gap_ratio >= axis_ratio_min)
    transverse_u, transverse_v, axis = _right_handed_frame(axis)
    # No current support means no candidate axis, while a degenerate or
    # non-unique covariance retains its candidate axis for transparent slices.
    axial = np.dot(relative, axis) if axis is not None else np.full(count, np.nan)
    axial_slice_width = 2.0 * sphere_radius / slice_count
    slice_edges = np.linspace(-sphere_radius, sphere_radius, slice_count + 1)
    slice_centers = (slice_edges[:-1] + slice_edges[1:]) * 0.5

    slices: List[Dict[str, Any]] = []
    centroids_y: List[Optional[np.ndarray]] = []
    centroids_i: List[Optional[np.ndarray]] = []
    for index in range(slice_count):
        if index == slice_count - 1:
            in_slice = inside & (axial >= slice_edges[index]) & (axial <= slice_edges[index + 1])
        else:
            in_slice = inside & (axial >= slice_edges[index]) & (axial < slice_edges[index + 1])
        y_stats = _weighted_channel_stats(relative, axis, sphere_center, y_current, y_norm, y_weight, y_active & in_slice) if axis is not None else {
            "site_count": 0, "weight_sum": None, "centroid": None, "width": None,
            "effective_n": None, "mean_current": None, "mean_current_norm": None,
            "current_coherence": None,
        }
        i_stats = _weighted_channel_stats(relative, axis, sphere_center, i_current, i_norm, i_weight, i_active & in_slice) if axis is not None else {
            "site_count": 0, "weight_sum": None, "centroid": None, "width": None,
            "effective_n": None, "mean_current": None, "mean_current_norm": None,
            "current_coherence": None,
        }
        centroids_y.append(y_stats["centroid"])
        centroids_i.append(i_stats["centroid"])
        slices.append({
            "index": index,
            "axial_bounds": [float(slice_edges[index]), float(slice_edges[index + 1])],
            "axial_center": float(slice_centers[index]),
            "site_count": int(np.count_nonzero(in_slice)),
            "support_site_count_y": int(y_stats["site_count"]),
            "support_site_count_i": int(i_stats["site_count"]),
            "centroid_y": _vector(y_stats["centroid"]),
            "centroid_i": _vector(i_stats["centroid"]),
            "weight_sum_y": _scalar(y_stats["weight_sum"]),
            "weight_sum_i": _scalar(i_stats["weight_sum"]),
            "effective_n_y": _scalar(y_stats["effective_n"]),
            "effective_n_i": _scalar(i_stats["effective_n"]),
            "width_y": _scalar(y_stats["width"]),
            "width_i": _scalar(i_stats["width"]),
            "mean_current_y": _vector(y_stats["mean_current"]),
            "mean_current_i": _vector(i_stats["mean_current"]),
            "mean_current_norm_y": _scalar(y_stats["mean_current_norm"]),
            "mean_current_norm_i": _scalar(i_stats["mean_current_norm"]),
            "coherence_y": _scalar(y_stats["current_coherence"]),
            "coherence_i": _scalar(i_stats["current_coherence"]),
        })

    tangents_y = _centroid_tangents(centroids_y, axis, slice_centers) if axis is not None else [None] * slice_count
    tangents_i = _centroid_tangents(centroids_i, axis, slice_centers) if axis is not None else [None] * slice_count
    resolved_mask: List[bool] = []
    resolved_reasons: List[List[str]] = []
    separation_vectors: List[Optional[np.ndarray]] = []
    separation_values: List[Optional[float]] = []
    for index, item in enumerate(slices):
        item["centroid_tangent_y"] = _vector(tangents_y[index])
        item["centroid_tangent_i"] = _vector(tangents_i[index])
        mean_y = np.asarray(item["mean_current_y"], dtype=np.float64) if item["mean_current_y"] is not None else None
        mean_i = np.asarray(item["mean_current_i"], dtype=np.float64) if item["mean_current_i"] is not None else None
        tangent_y = tangents_y[index]
        tangent_i = tangents_i[index]
        alignment_y = None if mean_y is None or tangent_y is None else _scalar(abs(float(np.dot(_unit(mean_y), tangent_y)))) if _unit(mean_y) is not None else None
        alignment_i = None if mean_i is None or tangent_i is None else _scalar(abs(float(np.dot(_unit(mean_i), tangent_i)))) if _unit(mean_i) is not None else None
        item["tangent_alignment_y"] = alignment_y
        item["tangent_alignment_i"] = alignment_i
        item["tangent_alignment_pass_y"] = None if alignment_y is None else bool(alignment_y >= tangent_min)
        item["tangent_alignment_pass_i"] = None if alignment_i is None else bool(alignment_i >= tangent_min)
        projection_y = None if mean_y is None else float(np.dot(mean_y, axis)) if axis is not None else None
        projection_i = None if mean_i is None else float(np.dot(mean_i, axis)) if axis is not None else None
        direction_y = None if projection_y is None or abs(projection_y) <= current_floor else float(np.sign(projection_y))
        direction_i = None if projection_i is None or abs(projection_i) <= current_floor else float(np.sign(projection_i))
        item["mean_current_axial_y"] = projection_y
        item["mean_current_axial_i"] = projection_i
        item["axial_direction_y"] = direction_y
        item["axial_direction_i"] = direction_i
        opposing = None if direction_y is None or direction_i is None else bool(direction_y * direction_i < 0.0)
        item["opposing_axial_directions"] = opposing
        item["coherence_pass_y"] = None if item["coherence_y"] is None else bool(item["coherence_y"] >= coherence_min)
        item["coherence_pass_i"] = None if item["coherence_i"] is None else bool(item["coherence_i"] >= coherence_min)

        centroid_y = centroids_y[index]
        centroid_i = centroids_i[index]
        separation = None
        separation_vector = None
        if centroid_y is not None and centroid_i is not None and axis is not None:
            full_vector = centroid_i - centroid_y
            separation_vector = full_vector - float(np.dot(full_vector, axis)) * axis
            separation = float(np.linalg.norm(separation_vector))
        separation_vectors.append(separation_vector)
        separation_values.append(separation)
        width_y = item["width_y"]
        width_i = item["width_i"]
        effective_y = item["effective_n_y"]
        effective_i = item["effective_n_i"]
        combined_width = None if width_y is None or width_i is None else math.sqrt(width_y * width_y + width_i * width_i)
        sep_over_spacing = None if separation is None else separation / grid_spacing
        sep_over_width = None if separation is None or combined_width is None or combined_width <= 0.0 else separation / combined_width
        slice_width = axial_slice_width
        slice_width_ratio = slice_width / grid_spacing
        width_ratio_y = None if width_y is None else width_y / grid_spacing
        width_ratio_i = None if width_i is None else width_i / grid_spacing
        pass_effective_y = None if effective_y is None else bool(effective_y >= effective_sites_min)
        pass_effective_i = None if effective_i is None else bool(effective_i >= effective_sites_min)
        pass_slice_width = bool(slice_width_ratio >= width_spacing_min)
        pass_sep_spacing = None if sep_over_spacing is None else bool(sep_over_spacing >= separation_spacing_min)
        if separation is None or combined_width is None:
            pass_sep_width = None
        else:
            # A coincident zero-width pair cannot be resolved.  A nonzero
            # separation from an exactly zero-width channel is mathematically
            # unambiguous, but its ratio remains None to expose the denominator.
            pass_sep_width = bool(separation > 0.0 and (combined_width <= 0.0 or sep_over_width >= separation_width_min))
        eligibility = {
            "effective_n_y": {"value": effective_y, "threshold": effective_sites_min, "passed": pass_effective_y},
            "effective_n_i": {"value": effective_i, "threshold": effective_sites_min, "passed": pass_effective_i},
            "slice_width_over_spacing": {"value": slice_width_ratio, "threshold": width_spacing_min, "passed": pass_slice_width},
            "separation_over_spacing": {"value": sep_over_spacing, "threshold": separation_spacing_min, "passed": pass_sep_spacing},
            "separation_over_width": {"value": sep_over_width, "threshold": separation_width_min, "passed": pass_sep_width},
        }
        item["slice_width"] = slice_width
        item["slice_width_over_spacing"] = slice_width_ratio
        item["transverse_width_over_spacing_y"] = width_ratio_y
        item["transverse_width_over_spacing_i"] = width_ratio_i
        item["separation_vector"] = _vector(separation_vector)
        item["separation"] = separation
        item["combined_width"] = combined_width
        item["separation_over_spacing"] = sep_over_spacing
        item["separation_over_width"] = sep_over_width
        item["eligibility"] = eligibility
        reasons: List[str] = []
        for label, result in eligibility.items():
            if result["passed"] is None:
                reasons.append(f"{label}: unavailable")
            elif not result["passed"]:
                reasons.append(f"{label}: below frozen threshold")
        resolved = all(value is True for value in (
            pass_effective_y, pass_effective_i, pass_slice_width,
            pass_sep_spacing, pass_sep_width,
        ))
        if not resolved and not reasons:
            reasons.append("resolved-pair predicate failed")
        item["resolved"] = bool(resolved)
        item["resolved_reasons"] = reasons
        resolved_mask.append(bool(resolved))
        resolved_reasons.append(reasons)

    for index, item in enumerate(slices):
        # Lists are filled after all centroids are available, so the tangent
        # estimate can use both neighboring slices without selecting another
        # axis or a nonconsecutive run.
        item["centroid_tangent_y"] = _vector(tangents_y[index])
        item["centroid_tangent_i"] = _vector(tangents_i[index])

    run_start, run_length, run_end = _longest_true_run(resolved_mask)
    run_indices = list(range(run_start, run_end + 1)) if run_end is not None else []
    winding_angles: List[Optional[float]] = []
    winding_unwrapped: List[Optional[float]] = []
    winding_turns: Optional[float] = None
    winding_signed_turns: Optional[float] = None
    winding_fit_slope: Optional[float] = None
    winding_fit_intercept: Optional[float] = None
    winding_fit_r2: Optional[float] = None
    winding_adjacent_increments: List[float] = []
    winding_monotonic_fraction: Optional[float] = None
    adjacent_angle_abs_max_measured: Optional[float] = None
    alias_risk: Optional[bool] = None
    winding_reason: List[str] = []
    winding_angle_valid = False
    if axis is not None and transverse_u is not None and transverse_v is not None and run_length >= 2:
        raw_angles: List[float] = []
        for index in run_indices:
            vector = separation_vectors[index]
            if vector is None or float(np.linalg.norm(vector)) <= 0.0:
                raw_angles = []
                break
            raw_angles.append(float(math.atan2(np.dot(vector, transverse_v), np.dot(vector, transverse_u))))
        if len(raw_angles) == run_length:
            winding_angle_valid = True
            winding_angles = raw_angles
            unwrapped = np.unwrap(np.asarray(raw_angles, dtype=np.float64))
            winding_unwrapped = [float(value) for value in unwrapped]
            if run_length >= 2:
                principal = np.angle(np.exp(1j * np.diff(np.asarray(raw_angles, dtype=np.float64))))
                winding_adjacent_increments = [float(value) for value in principal]
                adjacent_angle_abs_max_measured = float(np.max(np.abs(principal)))
                alias_risk = bool(np.any(np.abs(principal) >= angle_limit))
                fit_x = slice_centers[np.asarray(run_indices, dtype=int)]
                fit_y = unwrapped
                slope, intercept = np.polyfit(fit_x, fit_y, 1)
                winding_fit_slope = float(slope)
                winding_fit_intercept = float(intercept)
                predicted = slope * fit_x + intercept
                total_variation = float(np.sum((fit_y - np.mean(fit_y)) ** 2))
                residual = float(np.sum((fit_y - predicted) ** 2))
                if total_variation > 0.0:
                    winding_fit_r2 = float(max(0.0, min(1.0, 1.0 - residual / total_variation)))
                if abs(float(slope)) > 0.0:
                    signed = 1.0 if slope > 0.0 else -1.0
                    winding_monotonic_fraction = float(np.mean(signed * np.asarray(principal) > 0.0))
                winding_signed_turns = float((unwrapped[-1] - unwrapped[0]) / (2.0 * math.pi))
                winding_turns = abs(winding_signed_turns)
        else:
            winding_reason.append("coincident or unavailable separation in resolved run")
    elif run_length < 2:
        winding_reason.append("fewer than two resolved slices for winding")
    else:
        winding_reason.append("axis/transverse frame unavailable for winding")

    if run_length < minimum_run:
        winding_reason.append("longest resolved run is shorter than minimum consecutive slices")
    if winding_turns is None:
        winding_reason.append("winding turns unavailable")
    elif winding_turns < winding_turns_min:
        winding_reason.append("winding span is below the half-turn threshold")
    if adjacent_angle_abs_max_measured is None:
        adjacent_pass: Optional[bool] = None
        winding_reason.append("adjacent alias check unavailable")
    else:
        adjacent_pass = not alias_risk
        if alias_risk:
            winding_reason.append("adjacent separation angle reaches the alias limit")
    if winding_fit_r2 is None:
        fit_pass: Optional[bool] = None
    else:
        fit_pass = bool(winding_fit_r2 >= fit_r2_min)
        if not fit_pass:
            winding_reason.append("linear winding fit R2 is below threshold")
    if winding_monotonic_fraction is None:
        monotonic_pass: Optional[bool] = None
    else:
        monotonic_pass = bool(winding_monotonic_fraction >= monotonic_min)
        if not monotonic_pass:
            winding_reason.append("winding increments are not monotonic enough")
    run_pass = bool(run_length >= minimum_run and winding_angle_valid)
    half_turn_pass = None if winding_turns is None else bool(winding_turns >= winding_turns_min)
    winding_pass = bool(run_pass and half_turn_pass is True and adjacent_pass is True and fit_pass is True and monotonic_pass is True)

    resolved_indices = [index for index, value in enumerate(resolved_mask) if value]
    resolved_count = len(resolved_indices)
    coherence_failures: List[str] = []
    tangent_failures: List[str] = []
    opposing_count = 0
    opposing_eligible = 0
    for index in resolved_indices:
        item = slices[index]
        if item["coherence_pass_y"] is not True:
            coherence_failures.append(f"slice {index}: Y current coherence unavailable or below threshold")
        if item["coherence_pass_i"] is not True:
            coherence_failures.append(f"slice {index}: I current coherence unavailable or below threshold")
        if item["tangent_alignment_pass_y"] is not True:
            tangent_failures.append(f"slice {index}: Y tangent alignment unavailable or below threshold")
        if item["tangent_alignment_pass_i"] is not True:
            tangent_failures.append(f"slice {index}: I tangent alignment unavailable or below threshold")
        opposing = item["opposing_axial_directions"]
        if opposing is not None:
            opposing_eligible += 1
            if opposing:
                opposing_count += 1
    coherence_pass: Optional[bool] = None if resolved_count == 0 else not coherence_failures
    tangent_pass: Optional[bool] = None if resolved_count == 0 else not tangent_failures
    counterdirected_fraction: Optional[float] = None if resolved_count == 0 else float(opposing_count / resolved_count)
    counterdirected_pass: Optional[bool] = None if counterdirected_fraction is None else bool(counterdirected_fraction >= counterdirected_min)
    current_reasons = coherence_failures + tangent_failures
    if counterdirected_pass is False:
        current_reasons.append("resolved slices do not carry opposing axial directions")

    reasons: List[str] = []
    if count == 0:
        reasons.append("no sites supplied")
    if not np.any(inside):
        reasons.append("no sites lie inside centered sphere")
    if y_support == 0:
        reasons.append("Y current has no above-floor support in sphere")
    if i_support == 0:
        reasons.append("I current has no above-floor support in sphere")
    if axis is None:
        reasons.append("combined current covariance has no candidate axis")
    elif not axis_identifiable:
        reasons.append("candidate axis fails the frozen uniqueness gap ratio")
    if run_length < minimum_run:
        reasons.append("resolved-pair run is too short")
    reasons.extend(winding_reason)
    reasons.extend(current_reasons)
    if not reasons and not winding_pass:
        reasons.append("paired-helix predicates did not all pass")

    predicate = {
        "axis_identifiable": axis_identifiable,
        "resolved_run": run_pass,
        "winding_half_turn": half_turn_pass,
        "winding_alias_free": adjacent_pass,
        "winding_fit_r2": fit_pass,
        "winding_monotonic": monotonic_pass,
        "current_coherence": coherence_pass,
        "tangent_alignment": tangent_pass,
        "counterdirected": counterdirected_pass,
    }
    detected = bool(all(value is True for value in predicate.values()))
    if not counterdirected_pass:
        # This explicit guard makes a helical coflow fail even if every spatial
        # winding and tangent metric is excellent.
        detected = False

    winding = {
        "run_indices": run_indices,
        "run_start": run_start if run_length else None,
        "run_end": run_end,
        "run_length": run_length,
        "minimum_consecutive_slices": minimum_run,
        "separation_angles": winding_angles,
        "unwrapped_separation_angles": winding_unwrapped,
        "adjacent_increments": winding_adjacent_increments,
        "adjacent_angle_abs_max": adjacent_angle_abs_max_measured,
        "adjacent_angle_limit": angle_limit,
        "alias_risk": alias_risk,
        "winding_signed_turns": winding_signed_turns,
        "winding_turns": winding_turns,
        "fit_slope": winding_fit_slope,
        "fit_intercept": winding_fit_intercept,
        "fit_r2": winding_fit_r2,
        "monotonic_fraction": winding_monotonic_fraction,
        "half_turn_pass": half_turn_pass,
        "alias_free_pass": adjacent_pass,
        "fit_pass": fit_pass,
        "monotonic_pass": monotonic_pass,
        "reasons": winding_reason,
    }

    return {
        "detected": detected,
        "axis_identifiable": axis_identifiable,
        "axis": _vector(axis),
        "candidate_axis": _vector(axis),
        "selected_axis_kind": selected_kind,
        "prolate_axis": _vector(prolate_axis),
        "oblate_axis": _vector(oblate_axis),
        "transverse_u": _vector(transverse_u),
        "transverse_v": _vector(transverse_v),
        "transverse_basis": None if transverse_u is None or transverse_v is None or axis is None else [_vector(transverse_u), _vector(transverse_v), _vector(axis)],
        "eigenvalues": None if eigenvalues is None else [float(value) for value in eigenvalues],
        "covariance_center": _vector(None if covariance_center is None else covariance_center + sphere_center),
        "covariance": None if covariance is None else [[float(value) for value in row] for row in covariance],
        "prolate_gap": prolate_gap,
        "oblate_gap": oblate_gap,
        "prolate_gap_ratio": prolate_gap_ratio,
        "oblate_gap_ratio": oblate_gap_ratio,
        "axis_gap_ratio": axis_gap_ratio,
        "axis_gap_threshold": axis_ratio_min,
        "covariance_center_relative": _vector(covariance_center),
        "covariance_center_world": _vector(None if covariance_center is None else covariance_center + sphere_center),
        "axis_candidate_diagnostics": {
            "prolate_gap": prolate_gap,
            "oblate_gap": oblate_gap,
            "prolate_gap_ratio": prolate_gap_ratio,
            "oblate_gap_ratio": oblate_gap_ratio,
            "selected_kind": selected_kind,
            "selected_gap_ratio": axis_gap_ratio,
            "axis_identifiable": axis_identifiable,
        },
        "sphere_center": _vector(sphere_center),
        "radius": sphere_radius,
        "spacing": grid_spacing,
        "sphere_site_count": int(np.count_nonzero(inside)),
        "axial_slice_width": axial_slice_width,
        "axial_slice_width_over_spacing": axial_slice_width / grid_spacing,
        "support_site_count_y": y_support,
        "support_site_count_i": i_support,
        "component_weight_max_y": y_max,
        "component_weight_max_i": i_max,
        "component_weight_floor_y": y_weight_floor,
        "component_weight_floor_i": i_weight_floor,
        "site_weight_relative_floor": relative_floor,
        "current_floor": current_floor,
        "slice_edges": [float(value) for value in slice_edges],
        "slice_centers": [float(value) for value in slice_centers],
        "slices": slices,
        "resolved_slice_count": resolved_count,
        "consecutive_resolved_count": run_length,
        "resolved_pair_mask": resolved_mask,
        "resolved_pair_count": resolved_count,
        "longest_consecutive_resolved_run": {
            "start": run_start if run_length else None,
            "end": run_end,
            "length": run_length,
            "minimum_required": minimum_run,
            "passes": run_pass,
        },
        "resolved_reasons": resolved_reasons,
        "winding": winding,
        "winding_turns": winding_turns,
        "alias_risk": False if alias_risk is None else bool(alias_risk),
        "winding_fit_r2": winding_fit_r2,
        "fit_r2": winding_fit_r2,
        "counterdirected_fraction": counterdirected_fraction,
        "counterdirected_eligible_slices": opposing_eligible,
        "counterdirected_count": opposing_count,
        "counterdirected_threshold": counterdirected_min,
        "predicate": predicate,
        "reasons": reasons,
    }


__all__ = ["measure_channels"]
