#!/usr/bin/env python3
"""Resolution-matched image-level comparison for the 2023 ALMA Betelgeuse panels."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


SOURCES = {
    "B6": "https://arxiv.org/html/2608.19339v2/Fig1a_BetelB6_SUR_v2.png",
    "B7": "https://arxiv.org/html/2608.19339v2/Fig1b_BetelB7_SUR_v2.png",
    "B8": "https://arxiv.org/html/2608.19339v2/Fig1c_BetelB8_SUR_v2.png",
}
BEAMS = {
    "B6": (19.6, 14.1, 47.0),
    "B7": (10.7, 9.5, 19.0),
    "B8": (7.7, 6.6, 2.0),
}
SOURCE_SIZE = (1320, 1020)
SKY_PANEL_BBOX = (174, 7, 1125, 958)
GRID_N = 951
SKY_HALF_WIDTH_MAS = 45.0
DISK_RADIUS_MAS = 21.0
ANALYSIS_RADIUS_MAS = 18.0
RADIAL_BIN_MAS = 1.0
COMPONENT_THRESHOLD_RMS = 0.75
SATURATION_LIMIT = 0.10
CORRELATION_FLOOR = 0.25
ROTATION_ANGLES = tuple(range(30, 360, 30))
MIN_COMMON_BEAMS = 20.0
MIN_COMPONENTS_PER_BAND = 5
FWHM_TO_SIGMA = 1.0 / (2.0 * math.sqrt(2.0 * math.log(2.0)))


def srgb_luminance(rgb_u8: np.ndarray) -> np.ndarray:
    srgb = rgb_u8.astype(np.float64) / 255.0
    linear = np.where(
        srgb <= 0.04045,
        srgb / 12.92,
        ((srgb + 0.055) / 1.055) ** 2.4,
    )
    return (
        0.2126 * linear[..., 0]
        + 0.7152 * linear[..., 1]
        + 0.0722 * linear[..., 2]
    )




def resize_float(image: np.ndarray, size: int = GRID_N) -> np.ndarray:
    pil = Image.fromarray(image.astype(np.float32), mode="F")
    return np.asarray(
        pil.resize((size, size), resample=Image.Resampling.BILINEAR),
        dtype=np.float64,
    )


def coordinate_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    axis = np.linspace(SKY_HALF_WIDTH_MAS, -SKY_HALF_WIDTH_MAS, GRID_N)
    x, y = np.meshgrid(axis, axis)
    pixel_mas = 2.0 * SKY_HALF_WIDTH_MAS / (GRID_N - 1)
    return x, y, np.hypot(x, y), pixel_mas


def beam_covariance(major_mas: float, minor_mas: float, pa_deg: float) -> np.ndarray:
    angle = math.radians(pa_deg)
    major = np.array([math.sin(angle), math.cos(angle)])
    minor = np.array([-math.cos(angle), math.sin(angle)])
    basis = np.column_stack((major, minor))
    variances = np.diag(
        [
            (major_mas * FWHM_TO_SIGMA) ** 2,
            (minor_mas * FWHM_TO_SIGMA) ** 2,
        ]
    )
    return basis @ variances @ basis.T


def convolve_covariance(image: np.ndarray, covariance_mas2: np.ndarray, pixel_mas: float) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(covariance_mas2)
    if eigenvalues.min() < -1e-9:
        raise ValueError(f"additional beam covariance is not positive semidefinite: {eigenvalues}")
    covariance = eigenvectors @ np.diag(np.maximum(eigenvalues, 0.0)) @ eigenvectors.T
    pad = image.shape[0] // 2
    padded = np.pad(image, pad, mode="constant")
    fy = np.fft.fftfreq(padded.shape[0], d=pixel_mas)
    fx = np.fft.fftfreq(padded.shape[1], d=pixel_mas)
    kx, ky = np.meshgrid(fx, fy)
    exponent = (
        covariance[0, 0] * kx * kx
        + 2.0 * covariance[0, 1] * kx * ky
        + covariance[1, 1] * ky * ky
    )
    transfer = np.exp(-2.0 * math.pi * math.pi * exponent)
    result = np.fft.ifft2(np.fft.fft2(padded) * transfer).real
    return result[pad : pad + image.shape[0], pad : pad + image.shape[1]]


def radial_residual(image: np.ndarray, radius: np.ndarray) -> tuple[np.ndarray, float]:
    analysis_mask = radius <= ANALYSIS_RADIUS_MAS
    median = float(np.median(image[analysis_mask]))
    if not math.isfinite(median) or median <= 0.0:
        raise ValueError("non-positive disk median")
    normalized = image / median
    bin_index = np.floor(radius / RADIAL_BIN_MAS).astype(np.int32)
    profile = np.zeros_like(normalized)
    for ring in range(int(math.ceil(SKY_HALF_WIDTH_MAS / RADIAL_BIN_MAS)) + 1):
        mask = bin_index == ring
        if np.any(mask):
            profile[mask] = np.median(normalized[mask])
    residual = normalized - profile
    residual -= float(np.mean(residual[analysis_mask]))
    rms = float(np.sqrt(np.mean(residual[analysis_mask] ** 2)))
    return residual, rms


def standardized_residual(image: np.ndarray, radius: np.ndarray) -> tuple[np.ndarray, float]:
    residual, rms = radial_residual(image, radius)
    if not math.isfinite(rms) or rms <= 1e-12:
        raise ValueError(f"invalid residual RMS: {rms}")
    mask = radius <= ANALYSIS_RADIUS_MAS
    standardized = np.zeros_like(residual)
    standardized[mask] = residual[mask] / rms
    return standardized, rms


def weighted_covariance(image: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    weights = np.maximum(image, 0.0)
    total = float(weights.sum())
    mx = float((weights * x).sum() / total)
    my = float((weights * y).sum() / total)
    dx, dy = x - mx, y - my
    return np.array(
        [
            [float((weights * dx * dx).sum() / total), float((weights * dx * dy).sum() / total)],
            [float((weights * dx * dy).sum() / total), float((weights * dy * dy).sum() / total)],
        ]
    )


def synthetic_checks() -> dict[str, object]:
    x, y, radius, pixel_mas = coordinate_grid()
    radial = np.exp(-(radius**2) / (2.0 * 12.0**2))
    _, radial_rms = radial_residual(radial, radius)
    radial_pass = radial_rms < 0.03

    covariances = {band: beam_covariance(*beam) for band, beam in BEAMS.items()}
    inv_b8 = np.linalg.inv(covariances["B8"])
    quadratic = (
        inv_b8[0, 0] * x * x
        + 2.0 * inv_b8[0, 1] * x * y
        + inv_b8[1, 1] * y * y
    )
    b8_point = np.exp(-0.5 * quadratic)
    matched = convolve_covariance(
        b8_point,
        covariances["B6"] - covariances["B8"],
        pixel_mas,
    )
    measured = weighted_covariance(matched, x, y)
    expected_eigenvalues = np.linalg.eigvalsh(covariances["B6"])
    measured_eigenvalues = np.linalg.eigvalsh(measured)
    relative_error = np.abs(measured_eigenvalues / expected_eigenvalues - 1.0)
    beam_pass = bool(np.max(relative_error) <= 0.05)
    return {
        "radial_profile": {
            "sigma_mas": 12.0,
            "residual_rms": radial_rms,
            "limit": 0.03,
            "pass": radial_pass,
        },
        "beam_match": {
            "expected_covariance_eigenvalues_mas2": expected_eigenvalues.tolist(),
            "measured_covariance_eigenvalues_mas2": measured_eigenvalues.tolist(),
            "relative_error": relative_error.tolist(),
            "limit": 0.05,
            "pass": beam_pass,
        },
        "pass": radial_pass and beam_pass,
    }


def download_source(band: str, url: str, directory: Path) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    request = urllib.request.Request(url, headers={"User-Agent": "CassiCosmos morphology probe/1"})
    retrieved = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
        final_url = response.geturl()
        content_type = response.headers.get_content_type()
    if not content_type.startswith("image/"):
        raise ValueError(f"{band} returned {content_type}, not an image")
    directory.mkdir(parents=True, exist_ok=True)
    source_path = directory / f"{band.lower()}_figure1.png"
    source_path.write_bytes(payload)
    with Image.open(io.BytesIO(payload)) as source:
        rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
    if (rgb.shape[1], rgb.shape[0]) != SOURCE_SIZE:
        raise ValueError(
            f"{band} raster geometry changed: {(rgb.shape[1], rgb.shape[0])}"
        )
    x0, y0, x1, y1 = SKY_PANEL_BBOX
    luminance = srgb_luminance(rgb)
    panel = resize_float(luminance[y0:y1, x0:x1])
    saturated = resize_float(
        (np.max(rgb[y0:y1, x0:x1], axis=2) >= 254).astype(np.float32)
    )
    provenance = {
        "band": band,
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "retrieved_utc": retrieved,
        "byte_count": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "raster_width": int(rgb.shape[1]),
        "raster_height": int(rgb.shape[0]),
        "sky_panel_bbox_xyxy": [x0, y0, x1, y1],
        "saved_path": source_path.as_posix(),
    }
    return panel, saturated, provenance


def pearson(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    av = a[mask]
    bv = b[mask]
    av = av - av.mean()
    bv = bv - bv.mean()
    denominator = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denominator <= 0.0:
        return 0.0
    return float(np.dot(av, bv) / denominator)


def pair_correlations(residuals: dict[str, np.ndarray], mask: np.ndarray) -> dict[str, float]:
    return {
        "B6_B7": pearson(residuals["B6"], residuals["B7"], mask),
        "B6_B8": pearson(residuals["B6"], residuals["B8"], mask),
        "B7_B8": pearson(residuals["B7"], residuals["B8"], mask),
    }


def component_summary(
    residual: np.ndarray,
    mask: np.ndarray,
    pixel_area_mas2: float,
    target_beam_area_mas2: float,
) -> dict[str, object]:
    labels, count = ndimage.label(
        (residual > COMPONENT_THRESHOLD_RMS) & mask,
        structure=np.ones((3, 3), dtype=np.uint8),
    )
    sizes = np.bincount(labels.ravel(), minlength=count + 1)[1:]
    areas_beams = sizes.astype(np.float64) * pixel_area_mas2 / target_beam_area_mas2
    retained = areas_beams[areas_beams >= 0.25]
    return {
        "raw_component_count": int(count),
        "minimum_area_target_beams": 0.25,
        "retained_component_count": int(retained.size),
        "retained_areas_target_beams": retained.tolist(),
    }


def rotate_residual(image: np.ndarray, angle: float, mask: np.ndarray) -> np.ndarray:
    rotated = ndimage.rotate(
        image,
        angle,
        reshape=False,
        order=1,
        mode="constant",
        cval=0.0,
        prefilter=False,
    )
    rotated[~mask] = 0.0
    return rotated


def run(output_path: Path) -> dict[str, object]:
    checks = synthetic_checks()
    print(f"GATE SYNTH_RADIAL {'PASS' if checks['radial_profile']['pass'] else 'FAIL'}")
    print(f"GATE SYNTH_BEAM_MATCH {'PASS' if checks['beam_match']['pass'] else 'FAIL'}")
    if not checks["pass"]:
        raise RuntimeError("synthetic harness check failed")

    source_dir = output_path.parent / "sources"
    panels: dict[str, np.ndarray] = {}
    saturation_maps: dict[str, np.ndarray] = {}
    provenance: dict[str, dict[str, object]] = {}
    for band, url in SOURCES.items():
        panels[band], saturation_maps[band], provenance[band] = download_source(
            band, url, source_dir
        )
    print("GATE INPUT_INTEGRITY PASS")

    x, y, radius, pixel_mas = coordinate_grid()
    analysis_mask = radius <= ANALYSIS_RADIUS_MAS
    disk_mask = radius <= DISK_RADIUS_MAS
    covariances = {band: beam_covariance(*beam) for band, beam in BEAMS.items()}
    target_covariance = covariances["B6"]
    matched: dict[str, np.ndarray] = {"B6": panels["B6"]}
    additional_covariances: dict[str, list[list[float]]] = {"B6": [[0.0, 0.0], [0.0, 0.0]]}
    for band in ("B7", "B8"):
        additional = target_covariance - covariances[band]
        if np.linalg.eigvalsh(additional).min() < -1e-9:
            raise RuntimeError(f"cannot match {band} to B6 beam")
        matched[band] = convolve_covariance(panels[band], additional, pixel_mas)
        additional_covariances[band] = additional.tolist()
    print("GATE RESOLUTION_MATCH PASS")

    residuals: dict[str, np.ndarray] = {}
    residual_rms: dict[str, float] = {}
    saturation_fraction: dict[str, float] = {}
    for band in SOURCES:
        residuals[band], residual_rms[band] = standardized_residual(matched[band], radius)
        saturation_fraction[band] = float(np.mean(saturation_maps[band][disk_mask]))
    raster_ok = max(saturation_fraction.values()) <= SATURATION_LIMIT
    print(f"GATE RASTER_SUITABILITY {'PASS' if raster_ok else 'FAIL'}")

    correlations = pair_correlations(residuals, analysis_mask)
    mean_correlation = float(np.mean(list(correlations.values())))
    null_values: list[float] = []
    rotated_b7 = {
        angle: rotate_residual(residuals["B7"], angle, analysis_mask)
        for angle in ROTATION_ANGLES
    }
    rotated_b8 = {
        angle: rotate_residual(residuals["B8"], angle, analysis_mask)
        for angle in ROTATION_ANGLES
    }
    for angle7 in ROTATION_ANGLES:
        for angle8 in ROTATION_ANGLES:
            candidate = {
                "B6": residuals["B6"],
                "B7": rotated_b7[angle7],
                "B8": rotated_b8[angle8],
            }
            null_values.append(float(np.mean(list(pair_correlations(candidate, analysis_mask).values()))))
    null_95 = float(np.percentile(null_values, 95.0))

    target_beam_area = math.pi * BEAMS["B6"][0] * BEAMS["B6"][1] / (4.0 * math.log(2.0))
    pixel_area = pixel_mas * pixel_mas
    components = {
        band: component_summary(
            residuals[band], analysis_mask, pixel_area, target_beam_area
        )
        for band in SOURCES
    }
    beam_counts = {
        band: 4.0
        * math.log(2.0)
        * DISK_RADIUS_MAS**2
        / (beam[0] * beam[1])
        for band, beam in BEAMS.items()
    }
    common_beam_count = beam_counts["B6"]

    o1_conditions = {
        "all_pair_correlations_at_least_floor": min(correlations.values()) >= CORRELATION_FLOOR,
        "registered_mean_above_rotation_null_p95": mean_correlation > null_95,
        "component_in_every_band": all(
            summary["retained_component_count"] >= 1 for summary in components.values()
        ),
        "raster_saturation_acceptable": raster_ok,
    }
    if not raster_ok:
        o1 = "INCONCLUSIVE_RASTER_SATURATION"
    elif all(o1_conditions.values()):
        o1 = "SUPPORTS_RESOLUTION_STABLE_NONAXISYMMETRY"
    else:
        o1 = "DOES_NOT_SUPPORT_RESOLUTION_STABLE_NONAXISYMMETRY"

    enough_beams = common_beam_count >= MIN_COMMON_BEAMS
    enough_components = all(
        summary["retained_component_count"] >= MIN_COMPONENTS_PER_BAND
        for summary in components.values()
    )
    if enough_beams and enough_components:
        o2 = "INCONCLUSIVE_NO_CASSI_FORWARD_MODEL"
    else:
        o2 = "INCONCLUSIVE_LOW_MORPHOLOGY_COUNT"

    report = {
        "schema": "cassi.betelgeuse-morphology.v1",
        "preregistration": "research/stellar_cells/betelgeuse_morphology_prereg.md",
        "paper": {
            "title": "ALMA high-resolution observations of Betelgeuse: Persistent structure spanning the inner atmosphere",
            "authors_lead": "W. R. F. Dent et al.",
            "arxiv": "2608.19339v2",
            "paper_url": "https://arxiv.org/abs/2608.19339",
            "eso_image_id": "potw2634a",
            "eso_url": "https://eso.org/public/images/potw2634a/",
        },
        "provenance": provenance,
        "constants": {
            "grid_n": GRID_N,
            "sky_half_width_mas": SKY_HALF_WIDTH_MAS,
            "disk_radius_mas": DISK_RADIUS_MAS,
            "analysis_radius_mas": ANALYSIS_RADIUS_MAS,
            "radial_bin_mas": RADIAL_BIN_MAS,
            "component_threshold_rms": COMPONENT_THRESHOLD_RMS,
            "saturation_limit": SATURATION_LIMIT,
            "correlation_floor": CORRELATION_FLOOR,
            "rotation_angles_deg": ROTATION_ANGLES,
            "minimum_common_beams": MIN_COMMON_BEAMS,
            "minimum_components_per_band": MIN_COMPONENTS_PER_BAND,
            "beams_major_minor_pa_deg": BEAMS,
        },
        "synthetic_checks": checks,
        "resolution_match": {
            "target_band": "B6",
            "additional_covariances_mas2": additional_covariances,
            "independent_beam_areas_in_nominal_disk": beam_counts,
            "common_resolution_independent_beam_areas": common_beam_count,
        },
        "raster": {
            "residual_rms_before_standardization": residual_rms,
            "saturation_fraction_in_nominal_disk": saturation_fraction,
        },
        "statistics": {
            "pair_correlations": correlations,
            "mean_pair_correlation": mean_correlation,
            "rotation_null_count": len(null_values),
            "rotation_null_mean": float(np.mean(null_values)),
            "rotation_null_p95": null_95,
            "positive_components": components,
        },
        "gates": {
            "o1_conditions": o1_conditions,
            "o2_enough_common_beams": enough_beams,
            "o2_enough_components": enough_components,
        },
        "verdicts": {
            "O1_cross_band_nonaxisymmetry": o1,
            "O2_cassi_specific_cellular_grid": o2,
            "O3_proton_star_identity": "NOT_TESTED_BY_THIS_OBSERVATION",
        },
        "limitations": [
            "Rendered, monotone-color Figure 1 rasters are not calibrated FITS brightness maps.",
            "The B6 common resolution supplies only a few independent beam areas across the disk.",
            "Restoring beams round and correlate beam-scale features.",
            "Shared normalized morphology does not identify convection, Cassi dynamics, or any other mechanism.",
            "No Cassi forward model or proton observable is compared in this probe.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("GATE REPORT_WRITTEN PASS")
    print(f"VERDICT O1 {o1}")
    print(f"VERDICT O2 {o2}")
    print("VERDICT O3 NOT_TESTED_BY_THIS_OBSERVATION")
    if raster_ok:
        print("ALL CHECKS PASSED")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("_diag/stellar_cells/betelgeuse_morphology.json"),
    )
    args = parser.parse_args()
    run(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
