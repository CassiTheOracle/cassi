"""Bounded, provenance-preserving features for immutable field-owned visual pages.

The adapter reads sensor pixels only from the field owner's page API. It does not
own persistent memory, decode user-supplied paths, or claim that a token-only
brain can interpret images.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from collections.abc import Mapping
from typing import Any


VISUAL_CAPABILITY_SCHEMA = "cassi.surface.visual-capability.v1"
VISUAL_REQUEST_SCHEMA = "cassi.surface.visual-request-result.v1"
VISUAL_FEATURE_SCHEMA = "cassi.surface.visual-page-features.v1"
MAX_VISUAL_PAGE_BYTES = 16 * 1024 * 1024
MAX_VISUAL_DIMENSION = 8192
READ_CHUNK_BYTES = 1024 * 1024

_PIXEL_FORMATS: dict[str, tuple[int, str]] = {
    "rgb24": (3, "rgb"),
    "bgr24": (3, "bgr"),
    "rgba8": (4, "rgba"),
    "rgba8888": (4, "rgba"),
    "bgra8": (4, "bgra"),
    "bgra8888": (4, "bgra"),
    "gray8": (1, "gray"),
    "rgb8": (3, "rgb"),
    "bgr8": (3, "bgr"),
    "grey8": (1, "gray"),
}


def unsupported_visual_capability(
    *,
    model_id: str,
    model_sha256: str | None,
    architecture: str | None,
    runtime_id: str,
    input_transport: str,
    reason_code: str,
    reason: str,
    model_capability: str = "unverified",
) -> dict[str, Any]:
    """Describe the selected route's actual visual-input boundary fail-closed."""

    model: dict[str, Any] = {"id": str(model_id)}
    if model_sha256 is not None:
        model["sha256"] = str(model_sha256)
    if architecture:
        model["architecture"] = str(architecture)
    return {
        "schema": VISUAL_CAPABILITY_SCHEMA,
        "status": "unsupported",
        "capability": "visual_input",
        "reason_code": str(reason_code),
        "reason": str(reason),
        "model_capability": str(model_capability),
        "model": model,
        "runtime": {
            "id": str(runtime_id),
            "input_transport": str(input_transport),
            "multimodal_api_verified": False,
        },
        "modalities": {
            "text": True,
            "image_pixels": False,
            "temporal_frames": False,
        },
        "limits": {"max_image_bytes": 0, "max_frames": 0},
        "provenance": {
            "pixels_forwarded": False,
            "image_identity": None,
            "visual_instrument": None,
        },
    }


def unsupported_visual_result(
    capability: Mapping[str, Any], *, requested_frames: int
) -> dict[str, Any]:
    """Return a machine-readable refusal; never convert the request to text."""

    return {
        "schema": VISUAL_REQUEST_SCHEMA,
        "status": "unsupported",
        "reason_code": capability.get("reason_code", "visual_input_unavailable"),
        "capability": dict(capability),
        "request": {
            "frames_requested": int(requested_frames),
            "submitted_to_brain": False,
            "pixels_forwarded": False,
            "text_only_fallback": False,
        },
        "content": None,
        "reasoning_content": None,
    }


def _integer(value: Any, label: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{label} is outside its supported bound")
    return value




def _rect(value: Any, width: int, height: int) -> tuple[int, int, int, int] | None:
    if isinstance(value, Mapping):
        x, y = value.get("x"), value.get("y")
        w, h = value.get("width"), value.get("height")
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        x, y, w, h = value
    else:
        return None
    try:
        x = _integer(x, "region x")
        y = _integer(y, "region y")
        w = _integer(w, "region width", minimum=1)
        h = _integer(h, "region height", minimum=1)
    except ValueError:
        return None
    if x + w > width or y + h > height:
        return None
    return x, y, w, h


def _rectangles(coverage: Mapping[str, Any], publication: Mapping[str, Any], width: int, height: int) -> tuple[list[tuple[int, int, int, int]], bool]:
    """Read privacy/missing regions in source pixels; unknown shapes redact all."""

    regions: list[tuple[int, int, int, int]] = []
    unknown = False
    names = ("redacted_regions", "missing_regions", "privacy_masks")
    for container in (coverage, publication):
        for name in names:
            raw = container.get(name, ())
            if raw is None or raw == () or raw == []:
                continue
            if not isinstance(raw, (list, tuple)):
                # Opaque values cannot locate safe pixels.
                unknown = True
                continue
            for item in raw:
                parsed = _rect(item, width, height)
                if parsed is None:
                    unknown = True
                else:
                    regions.append(parsed)
        raw_unknown = container.get("unknown_regions", ())
        if raw_unknown is not None and raw_unknown != () and raw_unknown != []:
            if isinstance(raw_unknown, (list, tuple)):
                for item in raw_unknown:
                    parsed = _rect(item, width, height)
                    if parsed is None:
                        unknown = True
                    else:
                        regions.append(parsed)
            else:
                unknown = True
        unknown_extent = container.get("unknown_extent")
        if unknown_extent is not None and unknown_extent is not False:
            unknown = True
    complete = coverage.get("complete")
    if complete is not True and complete is not False:
        unknown = True
    elif complete is False and not regions:
        unknown = True
    return regions, unknown
def _accessibility_transport_privacy(publication: Mapping[str, Any]) -> dict[str, Any]:
    accessibility = publication.get("accessibility")
    if accessibility is None:
        return {
            "accessibility_status": "not-captured",
            "structural_uncertainty": True,
            "privacy_mask": "authorized-source-and-explicit-pixel-coverage",
        }
    if not isinstance(accessibility, Mapping):
        raise _VisualPageUnavailable(
            "accessibility_metadata_invalid", "Surface accessibility metadata is invalid"
        )
    status = accessibility.get("status")
    if not isinstance(status, str) or not status:
        raise _VisualPageUnavailable(
            "accessibility_metadata_invalid", "Surface accessibility status is unknown"
        )
    if status != "available":
        return {
            "accessibility_status": status,
            "structural_uncertainty": True,
            "privacy_mask": "authorized-source-and-explicit-pixel-coverage",
        }

    nodes = accessibility.get("nodes")
    truncated = accessibility.get("truncated")
    if (
        not isinstance(nodes, list)
        or len(nodes) > 4096
        or not isinstance(truncated, bool)
    ):
        raise _VisualPageUnavailable(
            "accessibility_coverage_unknown",
            "Surface accessibility nodes or completeness marker are invalid",
            details={
                "accessibility_status": "available",
                "structural_uncertainty": True,
                "privacy_mask": "not-submitted-unknown-accessibility-coverage",
            },
        )

    password_nodes = 0
    malformed_bounds = False
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("password"), bool):
            raise _VisualPageUnavailable(
                "accessibility_password_state_unknown",
                "Surface accessibility node password state is unknown",
                details={
                    "accessibility_status": "available",
                    "structural_uncertainty": True,
                    "privacy_mask": "not-submitted-unknown-accessibility-coverage",
                },
            )
        if node["password"]:
            password_nodes += 1
        bounds = node.get("bounds")
        if "bounds" not in node or (bounds is not None and not isinstance(bounds, Mapping)):
            malformed_bounds = True

    if password_nodes:
        raise _VisualPageUnavailable(
            "password_node_frame_redacted",
            "A password UIA node has no proven transform to exact image pixels; the full frame was refused",
            details={
                "accessibility_status": "available",
                "structural_uncertainty": truncated,
                "password_node_count": password_nodes,
                "privacy_mask": "full-frame-password-uncertain-transform",
            },
        )
    if malformed_bounds:
        raise _VisualPageUnavailable(
            "accessibility_bounds_unknown",
            "Surface accessibility node bounds are malformed",
            details={
                "accessibility_status": "available",
                "structural_uncertainty": True,
                "privacy_mask": "not-submitted-unknown-accessibility-coverage",
            },
        )
    if truncated:
        raise _VisualPageUnavailable(
            "accessibility_tree_truncated",
            "Surface accessibility tree is incomplete; possible password nodes are unknown",
            details={
                "accessibility_status": "available",
                "structural_uncertainty": True,
                "privacy_mask": "not-submitted-unknown-accessibility-coverage",
            },
        )
    return {
        "accessibility_status": "available",
        "structural_uncertainty": False,
        "privacy_mask": "authorized-source-and-explicit-pixel-coverage",
    }




def _cell_bounds(index: int, count: int, extent: int) -> tuple[int, int]:
    return (index * extent) // count, ((index + 1) * extent) // count


def _cell_redacted(
    cell_x: int,
    cell_y: int,
    count: int,
    width: int,
    height: int,
    regions: list[tuple[int, int, int, int]],
) -> bool:
    x0, x1 = _cell_bounds(cell_x, count, width)[0], _cell_bounds(cell_x + 1, count, width)[0]
    y0, y1 = _cell_bounds(cell_y, count, height)[0], _cell_bounds(cell_y + 1, count, height)[0]
    return any(x < x1 and x + w > x0 and y < y1 and y + h > y0 for x, y, w, h in regions)


def _channel(pixel: memoryview, offset: int, layout: str) -> tuple[int, int, int]:
    if layout == "gray":
        value = pixel[offset]
        return value, value, value
    first, green, third = pixel[offset], pixel[offset + 1], pixel[offset + 2]
    if layout in {"bgr", "bgra"}:
        return third, green, first
    return first, green, third


def _features(pixels: bytearray, *, width: int, height: int, layout: str, bpp: int,
              regions: list[tuple[int, int, int, int]], redact_all: bool) -> list[dict[str, Any]]:
    grid = 4 if min(width, height) >= 4 else 2 if min(width, height) >= 2 else 1
    redacted = [redact_all or _cell_redacted(x, y, grid, width, height, regions)
                for y in range(grid) for x in range(grid)]
    sums = [[0, 0, 0] for _ in range(grid * grid)]
    counts = [0] * (grid * grid)
    if not redact_all:
        view = memoryview(pixels)
        for y in range(height):
            by = min(grid - 1, y * grid // height)
            row_offset = y * width * bpp
            for x in range(width):
                bx = min(grid - 1, x * grid // width)
                cell = by * grid + bx
                if redacted[cell]:
                    continue
                pixel_offset = row_offset + x * bpp
                if layout in {"rgba", "bgra"} and view[pixel_offset + 3] == 0:
                    continue
                r, g, b = _channel(view, pixel_offset, layout)
                sums[cell][0] += r
                sums[cell][1] += g
                sums[cell][2] += b
                counts[cell] += 1

    levels: list[dict[str, Any]] = []
    level = grid
    while level:
        cells: list[dict[str, Any]] = []
        factor = grid // level
        for cy in range(level):
            y0, y1 = _cell_bounds(cy, level, height)
            for cx in range(level):
                x0, x1 = _cell_bounds(cx, level, width)
                base_cells = [
                    by * grid + bx
                    for by in range(cy * factor, (cy + 1) * factor)
                    for bx in range(cx * factor, (cx + 1) * factor)
                ]
                is_masked = any(redacted[index] for index in base_cells)
                total = [sum(sums[index][channel] for index in base_cells) for channel in range(3)]
                count = sum(counts[index] for index in base_cells)
                if is_masked or count == 0:
                    rgb = None
                    luma = None
                else:
                    rgb = [(value + count // 2) // count for value in total]
                    luma = (2126 * rgb[0] + 7152 * rgb[1] + 722 * rgb[2] + 5000) // 10000
                cells.append({
                    "bounds": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
                    "masked": bool(is_masked),
                    "mean_rgb8": rgb,
                    "mean_luma8": luma,
                })
        levels.append({"grid": level, "cells": cells})
        level //= 2
    return levels


def analyze_field_surface_page(owner: Any, publication: Mapping[str, Any]) -> dict[str, Any]:
    """Read one immutable field page and return bounded, deterministic crop features.

    The function accepts only an owner page reference. It never reads a caller
    filename, returns raw pixels, mutates the page, or writes an observation to
    adaptive memory. Privacy/missing regions are conservatively excluded.
    """

    if not isinstance(publication, Mapping):
        raise TypeError("surface publication must be a mapping")
    read_page = getattr(owner, "read_surface_page", None)
    if not callable(read_page):
        raise RuntimeError("field owner does not expose read_surface_page")
    binding_id = publication.get("binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        raise ValueError("surface publication lacks binding_id")
    generation = _integer(publication.get("generation"), "generation", minimum=1)
    width = _integer(publication.get("width"), "width", minimum=1, maximum=MAX_VISUAL_DIMENSION)
    height = _integer(publication.get("height"), "height", minimum=1, maximum=MAX_VISUAL_DIMENSION)
    pixel_format_value = publication.get("pixel_format")
    if not isinstance(pixel_format_value, str):
        raise ValueError("surface publication lacks pixel_format")
    pixel_format = pixel_format_value.strip().lower().replace("-", "").replace("_", "")
    aliases = {"rgba": "rgba8", "bgra": "bgra8", "gray": "gray8", "grey": "grey8"}
    pixel_format = aliases.get(pixel_format, pixel_format)
    descriptor = _PIXEL_FORMATS.get(pixel_format)
    if descriptor is None:
        raise ValueError(f"unsupported surface pixel format: {pixel_format_value}")
    bpp, layout = descriptor
    byte_length = _integer(publication.get("byte_length"), "byte_length", minimum=1,
                           maximum=MAX_VISUAL_PAGE_BYTES)
    expected_length = width * height * bpp
    if byte_length != expected_length:
        raise ValueError("surface page byte_length does not match its dimensions and pixel format")
    expected_sha256 = publication.get("sha256")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("surface publication lacks a SHA-256 pixel identity")
    coverage = publication.get("coverage")
    if not isinstance(coverage, Mapping):
        raise ValueError("surface publication lacks explicit coverage")

    pixels = bytearray(byte_length)
    digest = hashlib.sha256()
    for offset in range(0, byte_length, READ_CHUNK_BYTES):
        length = min(READ_CHUNK_BYTES, byte_length - offset)
        chunk = read_page(binding_id, generation, offset, length)
        if not isinstance(chunk, (bytes, bytearray, memoryview)) or len(chunk) != length:
            raise RuntimeError("field owner returned a truncated surface page range")
        digest.update(chunk)
        pixels[offset:offset + length] = chunk
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256.lower():
        raise RuntimeError("field surface page digest does not match its publication")

    regions, unknown_regions = _rectangles(coverage, publication, width, height)
    try:
        accessibility_privacy = _accessibility_transport_privacy(publication)
    except _VisualPageUnavailable as exc:
        accessibility_privacy = {
            **exc.details,
            "accessibility_refusal": exc.reason_code,
            "structural_uncertainty": True,
        }
        unknown_regions = True
    raw_instrument = publication.get("provenance")
    if raw_instrument is not None and (
        not isinstance(raw_instrument, str) or not raw_instrument
    ):
        raise ValueError("surface publication provenance is invalid")
    instrument = {
        "status": "provided" if raw_instrument is not None else "unavailable",
        "value": raw_instrument,
    }
    sample_time = publication.get("sample_time_ns")
    receipt_time = _integer(
        publication.get("receipt_time_ns"),
        "receipt_time_ns",
        minimum=1,
        maximum=(1 << 63) - 1,
    )
    if sample_time is not None:
        sample_time = _integer(
            sample_time, "sample_time_ns", maximum=(1 << 63) - 1
        )
    uncertainty = publication.get("sample_time_uncertainty_ns")
    if uncertainty is not None:
        uncertainty = _integer(
            uncertainty,
            "sample_time_uncertainty_ns",
            maximum=(1 << 63) - 1,
        )
    sequence = _integer(
        publication.get("sequence"), "sequence", minimum=1, maximum=(1 << 63) - 1
    )
    source_epoch = _integer(
        publication.get("source_epoch"),
        "source_epoch",
        minimum=1,
        maximum=(1 << 63) - 1,
    )
    geometry_revision = _integer(
        publication.get("geometry_revision"),
        "geometry_revision",
        maximum=(1 << 63) - 1,
    )
    environment_incarnation = publication.get("environment_incarnation")
    source_instance = publication.get("source_instance")
    source_id = publication.get("source_id")
    if not all(isinstance(value, str) and value for value in (
        source_instance, source_id, environment_incarnation,
    )):
        raise ValueError("surface publication lacks source provenance")
    receipt_clock_domain = publication.get("receipt_clock_domain")
    sample_clock_domain = publication.get("sample_clock_domain")
    for value, label in (
        (receipt_clock_domain, "receipt_clock_domain"),
        (sample_clock_domain, "sample_clock_domain"),
    ):
        if value is not None and (not isinstance(value, str) or not value):
            raise ValueError(f"surface publication {label} is invalid")
    features = _features(
        pixels, width=width, height=height, layout=layout, bpp=bpp,
        regions=regions, redact_all=unknown_regions,
    )
    feature_map = {
        f"grid_{level['grid']}": {
            f"cell_{index}": cell
            for index, cell in enumerate(level["cells"])
        }
        for level in features
    }
    image_identity = {
        "sha256": actual_sha256,
        "byte_length": byte_length,
        "width": width,
        "height": height,
        "pixel_format": pixel_format,
    }
    field_page_ref = {
        "binding_id": binding_id,
        "generation": generation,
        "sha256": actual_sha256,
    }
    source_metadata = {
        "binding_id": binding_id,
        "generation": generation,
        "source_id": source_id,
        "source_instance": source_instance,
        "source_epoch": source_epoch,
        "environment_incarnation": environment_incarnation,
        "geometry_revision": geometry_revision,
        "sequence": sequence,
    }
    clocks = {
        "sample_time_ns": sample_time,
        "sample_clock_domain": sample_clock_domain,
        "sample_time_uncertainty_ns": uncertainty,
        "receipt_time_ns": receipt_time,
        "receipt_clock_domain": receipt_clock_domain,
    }
    coverage_metadata = dict(coverage)
    observation = {
        **source_metadata,
        **clocks,
        "image_identity": image_identity,
        "field_page_ref": field_page_ref,
        "coverage": coverage_metadata,
        "instrument_provenance": instrument,
        "feature_method": "raw-pixel-mean-pyramid-v1",
        "features": feature_map,
        "feature_pyramid": features,
    }

    return {
        "schema": VISUAL_FEATURE_SCHEMA,
        "status": "features_ready",
        "feature_method": "raw-pixel-mean-pyramid-v1",
        "image_identity": image_identity,
        "field_page_ref": field_page_ref,
        "source": source_metadata,
        "clocks": clocks,
        "coverage": coverage_metadata,
        "observation": observation,
        "privacy": {
            "redacted_region_count": len(regions),
            **accessibility_privacy,
            "unknown_or_unlocalized_regions": unknown_regions,
            "redacted_cell_policy": "mask-intersecting-4x4-cells-and-all-ancestors",
            "raw_pixels_returned": False,
        },
        "instrument_provenance": instrument,
        "limits": {
            "max_page_bytes": MAX_VISUAL_PAGE_BYTES,
            "max_dimension": MAX_VISUAL_DIMENSION,
            "feature_levels": [level["grid"] for level in features],
            "pixels_forwarded_to_brain": False,
        },
        "features": feature_map,
        "feature_pyramid": features,
        "adaptive_memory_write": False,
    }



class _VisualPageUnavailable(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.details = dict(details or {})

def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _encode_field_surface_page(
    owner: Any,
    publication: Mapping[str, Any],
    *,
    program_id: str,
) -> dict[str, Any]:
    """Return one masked PNG read only through the current Surface page owner.

    The byte buffer exists only for this call and is never included in the
    returned provenance record. Unknown privacy geometry refuses the image
    rather than forwarding an unlocalised region.
    """

    if not isinstance(publication, Mapping):
        raise _VisualPageUnavailable("invalid_publication", "surface publication is invalid")
    if not isinstance(program_id, str) or not program_id:
        raise _VisualPageUnavailable("invalid_program_scope", "surface program scope is unavailable")
    read_page = getattr(owner, "read_surface_page", None)
    if not callable(read_page):
        raise _VisualPageUnavailable("field_page_reader_unavailable", "field owner cannot read Surface pages")

    binding_id = publication.get("binding_id")
    if not isinstance(binding_id, str) or not binding_id:
        raise _VisualPageUnavailable("invalid_publication", "surface publication lacks binding_id")
    try:
        generation = _integer(publication.get("generation"), "generation", minimum=1)
        width = _integer(
            publication.get("width"), "width", minimum=1, maximum=MAX_VISUAL_DIMENSION
        )
        height = _integer(
            publication.get("height"), "height", minimum=1, maximum=MAX_VISUAL_DIMENSION
        )
        byte_length = _integer(
            publication.get("byte_length"),
            "byte_length",
            minimum=1,
            maximum=MAX_VISUAL_PAGE_BYTES,
        )
    except ValueError as exc:
        raise _VisualPageUnavailable("invalid_publication", str(exc)) from exc

    pixel_format_value = publication.get("pixel_format")
    if not isinstance(pixel_format_value, str):
        raise _VisualPageUnavailable("invalid_publication", "surface publication lacks pixel_format")
    pixel_format = pixel_format_value.strip().lower().replace("-", "").replace("_", "")
    aliases = {"rgba": "rgba8", "bgra": "bgra8", "gray": "gray8", "grey": "grey8"}
    pixel_format = aliases.get(pixel_format, pixel_format)
    descriptor = _PIXEL_FORMATS.get(pixel_format)
    if descriptor is None:
        raise _VisualPageUnavailable("unsupported_pixel_format", "surface pixel format is unsupported")
    bpp, layout = descriptor
    if byte_length != width * height * bpp:
        raise _VisualPageUnavailable(
            "invalid_publication", "surface page length does not match its dimensions"
        )

    expected_sha256 = publication.get("sha256")
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in expected_sha256)
    ):
        raise _VisualPageUnavailable("invalid_publication", "surface publication lacks a valid SHA-256")
    coverage = publication.get("coverage")
    if not isinstance(coverage, Mapping):
        raise _VisualPageUnavailable("privacy_coverage_unavailable", "surface publication lacks coverage")
    if coverage.get("complete") is not True or any(
        not isinstance(coverage.get(name), list)
        for name in ("missing_regions", "redacted_regions", "unknown_regions")
    ):
        raise _VisualPageUnavailable(
            "privacy_coverage_incomplete",
            "Surface image coverage must explicitly report complete missing and redacted regions",
        )
    regions, unknown_regions = _rectangles(coverage, publication, width, height)
    if unknown_regions:
        raise _VisualPageUnavailable(
            "unknown_privacy_regions",
            "Surface privacy or missing-region geometry is unknown; pixels were not submitted",
        )
    if len(regions) > 1024:
        raise _VisualPageUnavailable(
            "privacy_region_limit", "Surface privacy geometry exceeds the supported bound"
        )
    accessibility_privacy = _accessibility_transport_privacy(publication)


    pixels = bytearray(byte_length)
    digest = hashlib.sha256()
    for offset in range(0, byte_length, READ_CHUNK_BYTES):
        length = min(READ_CHUNK_BYTES, byte_length - offset)
        try:
            chunk = read_page(
                binding_id,
                generation,
                offset,
                length,
                program_id=program_id,
            )
        except Exception as exc:
            raise _VisualPageUnavailable(
                "field_page_read_failed", "field owner refused the Surface page read"
            ) from exc
        if not isinstance(chunk, (bytes, bytearray, memoryview)) or len(chunk) != length:
            raise _VisualPageUnavailable(
                "field_page_read_failed", "field owner returned an incomplete Surface page range"
            )
        digest.update(chunk)
        pixels[offset:offset + length] = chunk
    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256.lower():
        raise _VisualPageUnavailable(
            "page_digest_mismatch", "Surface pixels do not match the published SHA-256"
        )


    masked = bytearray(width * height)
    for x, y, region_width, region_height in regions:
        span = b"\x01" * region_width
        for row in range(y, y + region_height):
            start = row * width + x
            masked[start:start + region_width] = span

    output_channels = 1 if layout == "gray" else 3
    color_type = 0 if output_channels == 1 else 2
    compressor = zlib.compressobj(level=6)
    compressed = bytearray()
    source_view = memoryview(pixels)
    for y in range(height):
        row = bytearray(width * output_channels)
        source_offset = y * width * bpp
        mask_offset = y * width
        for x in range(width):
            target_offset = x * output_channels
            if masked[mask_offset + x]:
                continue
            pixel_offset = source_offset + x * bpp
            if output_channels == 1:
                row[target_offset] = source_view[pixel_offset]
                continue
            red, green, blue = _channel(source_view, pixel_offset, layout)
            if layout in {"rgba", "bgra"}:
                alpha = source_view[pixel_offset + 3]
                red = (red * alpha + 127) // 255
                green = (green * alpha + 127) // 255
                blue = (blue * alpha + 127) // 255
            row[target_offset:target_offset + 3] = bytes((red, green, blue))
        compressed.extend(compressor.compress(b"\x00" + row))
    compressed.extend(compressor.flush())
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
        + _png_chunk(b"IDAT", bytes(compressed))
        + _png_chunk(b"IEND", b"")
    )
    if len(png) > MAX_VISUAL_PAGE_BYTES + 1024 * 1024:
        raise _VisualPageUnavailable(
            "encoded_image_limit", "sanitized Surface image exceeds the transport bound"
        )

    source_fields = {
        "source_id": publication.get("source_id"),
        "source_instance": publication.get("source_instance"),
        "source_epoch": publication.get("source_epoch"),
        "environment_incarnation": publication.get("environment_incarnation"),
        "geometry_revision": publication.get("geometry_revision"),
        "sequence": publication.get("sequence"),
    }
    if (
        not all(isinstance(source_fields[name], str) and source_fields[name] for name in (
            "source_id", "source_instance", "environment_incarnation"
        ))
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in (source_fields[name] for name in (
                "source_epoch", "geometry_revision", "sequence"
            ))
        )
        or source_fields["source_epoch"] == 0
        or source_fields["sequence"] == 0
    ):
        raise _VisualPageUnavailable("invalid_publication", "Surface source identity is incomplete")
    sample_time = publication.get("sample_time_ns")
    if sample_time is not None:
        try:
            sample_time = _integer(sample_time, "sample_time_ns", maximum=(1 << 63) - 1)
        except ValueError as exc:
            raise _VisualPageUnavailable("invalid_publication", str(exc)) from exc
    try:
        receipt_time = _integer(
            publication.get("receipt_time_ns"),
            "receipt_time_ns",
            minimum=1,
            maximum=(1 << 63) - 1,
        )
    except ValueError as exc:
        raise _VisualPageUnavailable("invalid_publication", str(exc)) from exc

    source = {
        **source_fields,
        "binding_id": binding_id,
        "generation": generation,
    }
    clocks = {
        "sample_time_ns": sample_time,
        "sample_clock_domain": publication.get("sample_clock_domain"),
        "sample_time_uncertainty_ns": publication.get("sample_time_uncertainty_ns"),
        "receipt_time_ns": receipt_time,
        "receipt_clock_domain": publication.get("receipt_clock_domain"),
    }
    image_identity = {
        "sha256": actual_sha256,
        "byte_length": byte_length,
        "width": width,
        "height": height,
        "pixel_format": pixel_format,
    }
    return {
        "image_bytes": png,
        "media_type": "image/png",
        "image_identity": image_identity,
        "sanitized_image": {
            "sha256": hashlib.sha256(png).hexdigest(),
            "byte_length": len(png),
            "media_type": "image/png",
            "width": width,
            "height": height,
        },
        "field_page_ref": {
            "binding_id": binding_id,
            "generation": generation,
            "sha256": actual_sha256,
        },
        "source": source,
        "clocks": clocks,
        "privacy": {
            "redacted_region_count": len(regions),
            **accessibility_privacy,
            "privacy_scope": "authorized-source-and-explicit-pixel-coverage",
            "unknown_or_unlocalized_regions": False,
            "redacted_pixel_policy": "opaque-black-exact-region",
            "raw_pixels_returned": False,
        },
    }


__all__ = [
    "MAX_VISUAL_DIMENSION",
    "MAX_VISUAL_PAGE_BYTES",
    "VISUAL_CAPABILITY_SCHEMA",
    "VISUAL_FEATURE_SCHEMA",
    "VISUAL_REQUEST_SCHEMA",
    "analyze_field_surface_page",
    "unsupported_visual_capability",
    "unsupported_visual_result",
]
