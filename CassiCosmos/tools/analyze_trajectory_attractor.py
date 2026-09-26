"""Cross-condition radial-layer analysis for the trajectory probe arms.

Implements the frozen rules of
`CassiCosmos/research/matter_formation/trajectory_general_attractor_prereg.md`:
per-arm late-window normalized radial profile, ridge detection with
prominence and reference matching, sphericity and concentration diagnostics,
and the registered verdicts. It reads only receipts and raw binary arrays and
reuses the registered analyzer's fail-closed reader and configuration check.

Run from the repository root:

    python tools/analyze_trajectory_attractor.py
    python tools/analyze_trajectory_attractor.py --run _diag/matter_formation/attractor_ic2 ...

Default arms are the eight registered directories. Every analyzed arm gets an
`analysis.json` beside its artifacts; the comparison is written to
`_diag/matter_formation/attractor_summary.json` and printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_trajectory_probe import (  # pyright: ignore[reportMissingImports]  # noqa: E402
    AnalysisFailure,
    _missing_registered_config,
    _read_exact,
)


def _json_safe(value: Any) -> Any:
    """Convert NumPy values and nonfinite floats to strict JSON values."""
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


## Frozen statistic constants (prereg §4).

BINS = 48
U_MAX = 3.0
U_MIN = 0.1
U_MAX_RIDGE = 2.5
PROMINENCE = 1.25
LATE_FRACTION = 0.75
MATCH_TOLERANCE = 0.15

## Frozen decision constants (prereg §5).
MIN_QUALIFYING_ARMS = 6
SUPPORT_MIN_ARMS_WITH_RIDGES = 6
SUPPORT_MIN_MATCHED_ARMS = 4
DOES_NOT_EMERGE_MAX_ARMS_WITH_RIDGES = 4
MIN_RIDGES_PER_ARM = 2

DEFAULT_ICS = (2, 3, 5, 7, 8, 10, 11, 6)
REFERENCE_IC = 6
DIAG_ROOT = Path("_diag/matter_formation")

## Descriptive phase-space stream diagnostic (not part of the frozen verdict).
## A caustic shell is a fold of the radial phase-space sheet: at radii inside a
## shell the particles split into distinct streams with different |v_r|, while a
## relaxed single-cloud remnant fills one broad band. For each radial bin the
## |v_r| distribution is compared against a single-population null (half-normal
## at the same rms) whose mode count is measured with the same kernel density
## estimator, so a reported stream count is an excess over what one stream
## produces at that sample size. With the 0.15-rms bandwidth validated against
## synthetic two- and three-stream populations, streams separated by at least
## about 0.5 rms speeds and carrying at least a third of the band mass are
## resolved; closer streams merge.
STREAM_SLOTS = 8            # most recent sample slots used
STREAM_RADIUS_LO = 0.3      # inner edge, in units of the late r50
STREAM_RADIUS_HI = 1.6      # outer edge, in units of the late r50
STREAM_RADIAL_BINS = 9
STREAM_GRID = 96
STREAM_BANDWIDTH = 0.15    # kernel bandwidth, in units of the band rms speed
STREAM_DIP_FRACTION = 0.1   # dip between modes, as a fraction of the lower peak
STREAM_NULL_REPLICATES = 128
STREAM_NULL_QUANTILE = 0.95

## Descriptive epoch timeline (not part of the frozen verdict): consecutive
## samples averaged in groups of this size, giving a shell history with roughly
## a fifth of the single-sample profile noise.
EPOCH_SAMPLES = 8

## Frozen configuration each arm must prove in its receipt (prereg §3). Keys are
## looked up in the receipt's `engine` block unless dotted. Values are compared
## numerically for numbers and by identity for booleans and strings.
PRIMARY_FROZEN: dict[str, Any] = {
    "N_particles": 8192,
    "grid_N": 64,
    "dt": 0.001,
    "gravity_mode": 5,
    "meshless_mode": True,
    "meshless_gravity": True,
    "freeze_field": True,
    "source_strength": 0.0,
    "num_clusters": 1,
    "cluster_separation": 0.0,
    "box_aspect": [1.0, 1.0, 1.0],
    "box_scale": 1.0,
    "window_center": [0.0, 0.0, 0.0],
    "initial_total_mass": 1000.0,
    "initial_radius_fraction": 0.9,
    "initial_arrangement": 0,
    "initial_motion": 1,
    "initial_speed": 1.0,
    "particle_merge": False,
    "black_holes_enabled": False,
    "bh_accretion": False,
    "dual_grid": False,
    "seed": 20260910,
    "softening": 0.1,
    "xi": 17.94427191,
    "cluster_radius": 25.0,
    "accepted_steps": 1_000_000,
    "recorder_enabled": True,
    "tracer_count": 4096,
    "sample_stride": 4096,
    "sample_capacity": 256,
    "event_capacity": 65536,
    "field_control.field_attractor_init": True,
}

## A registered input that is a derived quantity (the engine's own geometry
## fit) is registered as an inclusive band instead of an exact value.
class Band(NamedTuple):
    lo: float
    hi: float


## The app-fidelity battery (prereg §5). Every arm shares the base; the table
## overrides the inputs that distinguish the five arms.
APP_FIDELITY_BASE: dict[str, Any] = {
    "N_particles": 8192,
    "grid_N": 64,
    "dt": 0.05,
    "gravity_mode": 5,
    "meshless_mode": True,
    "meshless_gravity": True,
    "source_strength": 0.0,
    "box_aspect": [1.0, 1.0, 1.0],
    "window_center": [0.0, 0.0, 0.0],
    "initial_total_mass": 2_320_000.0,
    "initial_radius_fraction": 1.0,
    "initial_arrangement": 0,
    "initial_motion": 1,
    "initial_speed": 1.0,
    "particle_merge": False,
    "black_holes_enabled": False,
    "bh_accretion": False,
    "dual_grid": False,
    "seed": 20260910,
    "softening": 0.1,
    "xi": 17.94427191,
    "cluster_radius": 120.0,
    "accepted_steps": 100_000,
    "batch_steps": 2,
    "recorder_enabled": True,
    "tracer_count": 4096,
    "sample_stride": 400,
    "sample_capacity": 256,
    "event_capacity": 65536,
    "field_control.field_attractor_init": True,
    "tree_cadence": 250,
}

APP_FIDELITY_FROZEN: dict[str, dict[str, Any]] = {
    "A3": {
        "num_clusters": 3,
        "cluster_separation": 1500.0,
        "box_scale": Band(9.4, 9.9),
        "freeze_field": True,
        "initial_condition": 3,
    },
    "A6": {
        "num_clusters": 3,
        "cluster_separation": 1500.0,
        "box_scale": Band(9.4, 9.9),
        "freeze_field": True,
        "initial_condition": 6,
    },
    "C1": {
        "num_clusters": 1,
        "cluster_separation": 0.0,
        "box_scale": Band(0.74, 0.82),
        "freeze_field": True,
        "initial_condition": 3,
    },
    "C2": {
        "num_clusters": 1,
        "cluster_separation": 0.0,
        "box_scale": Band(9.4, 9.9),
        "freeze_field": True,
        "initial_condition": 3,
    },
    "L3": {
        "num_clusters": 3,
        "cluster_separation": 1500.0,
        "box_scale": Band(9.4, 9.9),
        "freeze_field": False,
        "initial_condition": 3,
    },
}
SCENE_CALIBRATED_BASE: dict[str, Any] = dict(
    APP_FIDELITY_BASE, river_calibrate_gn=True
)
SCENE_CALIBRATED_FROZEN: dict[str, dict[str, Any]] = {
    "G3": APP_FIDELITY_FROZEN["A3"],
    "G6": APP_FIDELITY_FROZEN["A6"],
    "GC1": APP_FIDELITY_FROZEN["C1"],
    "GC2": APP_FIDELITY_FROZEN["C2"],
    "GL3": APP_FIDELITY_FROZEN["L3"],
}



def expected_frozen(run_dir: Path) -> dict[str, Any]:
    """The registered expectation for an arm directory."""
    name = run_dir.name
    if name in SCENE_CALIBRATED_FROZEN:
        return dict(SCENE_CALIBRATED_BASE, **SCENE_CALIBRATED_FROZEN[name])
    if name in APP_FIDELITY_FROZEN:
        return dict(APP_FIDELITY_BASE, **APP_FIDELITY_FROZEN[name])
    if name.startswith("attractor_ic") and name[12:].isdigit():
        return dict(PRIMARY_FROZEN, initial_condition=int(name[12:]))
    raise AnalysisFailure(f"no frozen configuration is registered for '{name}'")


def _receipt_value(scope: dict[str, Any], key: str) -> Any:
    node: Any = scope
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


_MISSING = object()


def _verify_frozen(receipt: dict[str, Any], expected: dict[str, Any]) -> int:
    """Raise unless every registered input matches its receipt value.

    Values are looked up in the receipt's `engine` block and at the receipt root:
    the physics inputs live in the engine block, and the recorder and field
    blocks live at the root. A key recorded in both scopes must agree in both.
    """
    engine = receipt.get("engine")
    if not isinstance(engine, dict):
        raise AnalysisFailure("receipt has no engine block")
    checked = 0
    for key, want in expected.items():
        found = False
        for scope in (engine, receipt):
            node = _receipt_value(scope, key)
            if node is _MISSING:
                continue
            found = True
            if isinstance(want, bool):
                if not isinstance(node, bool) or node is not want:
                    raise AnalysisFailure(f"receipt {key}={node!r}, registered {want!r}")
            elif isinstance(want, Band):
                if isinstance(node, bool) or not isinstance(node, (int, float)):
                    raise AnalysisFailure(f"receipt {key}={node!r} is not numeric")
                if not (want.lo <= float(node) <= want.hi):
                    raise AnalysisFailure(
                        f"receipt {key}={node!r}, registered band [{want.lo}, {want.hi}]"
                    )
            elif isinstance(want, (int, float)):
                if isinstance(node, bool) or not isinstance(node, (int, float)):
                    raise AnalysisFailure(f"receipt {key}={node!r} is not numeric")
                if abs(float(node) - float(want)) > 1.0e-6 * max(1.0, abs(float(want))):
                    raise AnalysisFailure(f"receipt {key}={node!r}, registered {want!r}")
            elif isinstance(want, list):
                values = [float(value) for value in node] if isinstance(node, list) else []
                if len(values) != len(want) or any(
                    abs(value - float(target)) > 1.0e-6
                    for value, target in zip(values, want)
                ):
                    raise AnalysisFailure(f"receipt {key}={node!r}, registered {want!r}")
            elif node != want:
                raise AnalysisFailure(f"receipt {key}={node!r}, registered {want!r}")
        if not found:
            raise AnalysisFailure(f"receipt does not record '{key}'")
        checked += 1
    return checked


def _arm_dir(ic: int) -> Path:
    return DIAG_ROOT / f"attractor_ic{ic}"


def _receipt(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "receipt.json"
    if not path.is_file():
        raise AnalysisFailure("missing receipt.json")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnalysisFailure(f"invalid receipt.json: {exc}") from exc
    if receipt.get("schema") != "cassi.trajectory-probe.v1":
        raise AnalysisFailure("unsupported trajectory receipt schema")
    if receipt.get("mode") != "shell":
        raise AnalysisFailure("attractor arms must be shell-mode receipts")
    if receipt.get("recorder_enabled") is not True:
        raise AnalysisFailure("attractor arms require the recorder")
    missing = _missing_registered_config(receipt)
    if missing:
        raise AnalysisFailure(
            "receipt does not record the frozen configuration: " + ", ".join(missing)
        )
    return receipt


def _prominence(profile: np.ndarray, index: int) -> tuple[float, int]:
    """Peak over key saddle, plus the saddle bin index (prereg §4.5)."""
    peak = float(profile[index])
    left = peak
    left_index = index
    j = index - 1
    while j >= 0 and profile[j] < peak:
        if float(profile[j]) < left:
            left = float(profile[j])
            left_index = j
        j -= 1
    right = peak
    right_index = index
    j = index + 1
    while j < profile.size and profile[j] < peak:
        if float(profile[j]) < right:
            right = float(profile[j])
            right_index = j
        j += 1
    if left >= right:
        saddle = left
        saddle_index = left_index
    else:
        saddle = right
        saddle_index = right_index
    if saddle <= 0.0:
        return float("inf"), saddle_index
    return peak / saddle, saddle_index


def _ridges(profile: np.ndarray, centers: np.ndarray) -> list[dict[str, float]]:
    """Shell ridges: local maxima above the prominence floor inside the gate."""
    ridges: list[dict[str, float]] = []
    for index in range(1, profile.size - 1):
        value = float(profile[index])
        if value <= float(profile[index - 1]) or value < float(profile[index + 1]):
            continue
        if ridges and abs(centers[index] - ridges[-1]["u"]) < (centers[1] - centers[0]):
            if value > ridges[-1]["peak"]:
                ridges[-1] = {"u": float(centers[index]), "peak": value, "index": index}
            continue
        ratio, saddle_index = _prominence(profile, index)
        radius = float(centers[index])
        if ratio >= PROMINENCE and U_MIN <= radius <= U_MAX_RIDGE:
            ridges.append(
                {
                    "u": radius,
                    "peak": value,
                    "prominence": float(ratio),
                    "index": index,
                    "saddle_index": saddle_index,
                }
            )
    return ridges


def _kde_modes(samples: np.ndarray, v_max: float, bandwidth: float) -> list[float]:
    """Modes of a Gaussian kernel density estimate over [0, v_max].

    A candidate maximum counts as a mode when its topographic prominence (the
    height difference to the higher of the two neighbouring saddles) reaches
    `STREAM_DIP_FRACTION` of its own height.
    """
    if samples.size < 8 or v_max <= 0.0 or bandwidth <= 0.0:
        return []
    grid = np.linspace(0.0, v_max, STREAM_GRID)
    scaled = (grid[:, None] - samples[None, :]) / bandwidth
    density = np.exp(-0.5 * np.square(scaled)).sum(axis=1)
    peak = float(density.max())
    if peak <= 0.0:
        return []
    floor = peak * STREAM_DIP_FRACTION
    candidates = [
        index
        for index in range(1, density.size - 1)
        if density[index] >= floor
        and density[index] >= density[index - 1]
        and density[index] > density[index + 1]
    ]
    candidates.sort(key=lambda index: -float(density[index]))
    accepted: list[int] = []
    for index in candidates:
        height = float(density[index])
        lowest = 0.0
        for neighbour in accepted:
            low, high = (index, neighbour) if index < neighbour else (neighbour, index)
            saddle = float(density[low : high + 1].min())
            if saddle >= (1.0 - STREAM_DIP_FRACTION) * min(height, float(density[neighbour])):
                lowest = 0.0
                break
            lowest = max(lowest, saddle)
        if accepted and lowest <= 0.0:
            continue
        if height - lowest >= STREAM_DIP_FRACTION * height:
            accepted.append(index)
    return [float(grid[index]) for index in sorted(accepted)]


def _null_mode_counts(sample_size: int, bandwidth: float, v_max: float) -> np.ndarray:
    """Mode counts of single-stream populations (half-normal) at this size."""
    rng = np.random.default_rng(12345)
    counts = np.zeros(STREAM_NULL_REPLICATES, dtype=np.int64)
    for index in range(STREAM_NULL_REPLICATES):
        draws = np.abs(rng.normal(0.0, v_max / 2.5, size=sample_size))
        counts[index] = len(_kde_modes(draws, v_max, bandwidth))
    return counts


def _stream_diagnostic(
    radius: np.ndarray,
    radial_velocity: np.ndarray,
    valid: np.ndarray,
    sample_steps: np.ndarray,
    late_slots: list[int],
) -> dict[str, Any]:
    """Count radial phase-space streams inside the shell band, per late slot."""
    if not late_slots:
        return {"slots": 0}
    null: dict[int, np.ndarray] = {}
    per_slot: list[dict[str, Any]] = []
    for slot in late_slots[-STREAM_SLOTS:]:
        values = radius[slot][valid[slot]]
        speeds = np.abs(radial_velocity[slot][valid[slot]])
        if values.size < 64:
            continue
        r50 = float(np.median(values))
        if r50 <= 0.0:
            continue
        inner = STREAM_RADIUS_LO * r50
        outer = STREAM_RADIUS_HI * r50
        shell = (values >= inner) & (values <= outer)
        if int(shell.sum()) < 64:
            continue
        width = (outer - inner) / float(STREAM_RADIAL_BINS)
        v_rms = float(np.sqrt(np.mean(np.square(speeds[shell]))))
        if v_rms <= 0.0:
            continue
        v_max = 2.5 * v_rms
        per_bin: list[dict[str, Any]] = []
        for index in range(STREAM_RADIAL_BINS):
            low = inner + width * index
            high = low + width
            band = shell & (values >= low) & (values < high)
            count = int(band.sum())
            if count < 48:
                continue
            bandwidth = STREAM_BANDWIDTH * v_rms
            if bandwidth <= 0.0:
                continue
            modes = _kde_modes(speeds[band], v_max, bandwidth)
            if count not in null:
                null[count] = _null_mode_counts(count, bandwidth, v_max)
            null_counts = null[count]
            threshold = float(np.quantile(null_counts, STREAM_NULL_QUANTILE))
            per_bin.append(
                {
                    "u": float(0.5 * (low + high) / r50),
                    "count": count,
                    "modes": len(modes),
                    "modes_u": [round(float(mode) / v_rms, 3) for mode in modes],
                    "null_modes": float(np.median(null_counts)),
                    "single_stream_max": int(threshold),
                    "excess": bool(len(modes) > threshold),
                }
            )
        if not per_bin:
            continue
        modes_array = np.asarray([entry["modes"] for entry in per_bin], dtype=np.int64)
        per_slot.append(
            {
                "step": int(sample_steps[slot]),
                "bins": len(per_bin),
                "median_modes": float(np.median(modes_array)),
                "max_modes": int(modes_array.max()),
                "excess_bins": int(sum(1 for entry in per_bin if entry["excess"])),
                "per_bin": per_bin,
            }
        )
    if not per_slot:
        return {"slots": 0}
    medians = np.asarray([entry["median_modes"] for entry in per_slot], dtype=np.float64)
    excess = np.asarray([entry["excess_bins"] for entry in per_slot], dtype=np.float64)
    bins = np.asarray([entry["bins"] for entry in per_slot], dtype=np.float64)
    last = per_slot[-1]
    return {
        "slots": len(per_slot),
        "radius_band": [STREAM_RADIUS_LO, STREAM_RADIUS_HI],
        "median_modes": float(np.median(medians)),
        "max_modes": int(max(entry["max_modes"] for entry in per_slot)),
        "excess_bin_fraction": float(np.mean(excess / np.maximum(bins, 1.0))),
        "last_slot_modes": [int(entry["modes"]) for entry in last["per_bin"]],
        "last_slot_modes_u": [entry["modes_u"] for entry in last["per_bin"]],
        "per_slot": [
            {
                "step": entry["step"],
                "bins": entry["bins"],
                "median_modes": entry["median_modes"],
                "max_modes": entry["max_modes"],
                "excess_bins": entry["excess_bins"],
            }
            for entry in per_slot
        ],
    }


def _epoch_ridge_series(
    slot_profiles: dict[int, np.ndarray],
    centers: np.ndarray,
    sample_steps: np.ndarray,
    r50_series: list[float],
) -> list[dict[str, Any]]:
    """Ridge structure of epoch-averaged profiles across the whole run.

    Single-sample profiles carry roughly ten percent per-bin noise at this
    tracer count, so shells are resolved by averaging consecutive samples into
    epochs, the same way the frozen late-window profile is built.
    """
    slots = sorted(slot_profiles)
    if not slots:
        return []
    series: list[dict[str, Any]] = []
    for start in range(0, len(slots), EPOCH_SAMPLES):
        group = slots[start : start + EPOCH_SAMPLES]
        stack = np.stack([slot_profiles[slot] for slot in group], axis=0)
        profile = np.mean(stack, axis=0)
        if stack.shape[0] > 1:
            spread = np.std(stack, axis=0, ddof=1) / float(np.sqrt(stack.shape[0]))
        else:
            spread = np.zeros(profile.size, dtype=np.float64)
        ridges = _ridges(profile, centers)
        for ridge in ridges:
            peak_index = int(ridge.pop("index"))
            saddle_index = int(ridge.pop("saddle_index"))
            error = float(np.hypot(spread[peak_index], spread[saddle_index]))
            ridge["z"] = (
                float((ridge["peak"] - float(profile[saddle_index])) / error)
                if error > 0.0
                else float("inf")
            )
        series.append(
            {
                "epoch": len(series),
                "samples": len(group),
                "step_first": int(sample_steps[group[0]]),
                "step_last": int(sample_steps[group[-1]]),
                "r50_mean": float(np.mean([r50_series[slot] for slot in group])),
                "ridge_count": len(ridges),
                "ridges": [
                    {"u": round(float(ridge["u"]), 4), "prominence": round(float(ridge["prominence"]), 3), "z": round(float(ridge["z"]), 1)}
                    for ridge in ridges
                ],
            }
        )
    return series


def _sphericity(points: np.ndarray) -> dict[str, float]:
    if points.shape[0] < 3:
        return {"axis_ba": 0.0, "axis_ca": 0.0}
    centered = points - points.mean(axis=0, keepdims=True)
    covariance = centered.T @ centered / float(points.shape[0])
    eigenvalues = np.linalg.eigvalsh(covariance)
    major = float(np.sqrt(max(eigenvalues[2], 0.0)))
    if major <= 0.0:
        return {"axis_ba": 0.0, "axis_ca": 0.0}
    return {
        "axis_ba": float(np.sqrt(max(eigenvalues[1], 0.0)) / major),
        "axis_ca": float(np.sqrt(max(eigenvalues[0], 0.0)) / major),
    }


def analyze_arm(run_dir: Path, strict: bool = True) -> dict[str, Any]:
    """Measure one arm under the frozen rules; raises AnalysisFailure."""
    receipt = _receipt(run_dir)
    frozen_checked = _verify_frozen(receipt, expected_frozen(run_dir)) if strict else 0
    tracer_count = int(receipt["tracer_count"])
    sample_slots = int(receipt["sample_slots"])
    sample_capacity = int(receipt["sample_capacity"])
    sample_stride = int(receipt["sample_stride"])
    accepted_steps = int(receipt["accepted_steps"])
    initial_total_mass = float(receipt["initial_total_mass"])
    final_total_mass = float(receipt["final_total_mass"])
    if tracer_count < 1 or sample_slots < 1 or sample_slots > sample_capacity:
        raise AnalysisFailure("invalid sample dimensions in receipt")
    if int(receipt["sample_overflow"]) != 0:
        raise AnalysisFailure("sample ring overflow")
    if int(receipt["event_overflow"]) != 0:
        raise AnalysisFailure("event buffer overflow")
    if int(receipt["event_total"]) != int(receipt["event_records_stored"]):
        raise AnalysisFailure("event ledger truncated")
    relative_mass_error = abs(final_total_mass - initial_total_mass) / max(
        abs(initial_total_mass), 1.0e-30
    )
    if relative_mass_error > 1.0e-4:
        raise AnalysisFailure(f"mass closure error={relative_mass_error:.6f}")

    sample_steps = _read_exact(run_dir, "sample_steps.bin", np.dtype("<u4"), sample_slots)
    history_pos = _read_exact(
        run_dir, "history_pos.bin", np.dtype("<f4"), sample_slots * tracer_count * 4
    ).reshape(sample_slots, tracer_count, 4)
    history_vel = _read_exact(
        run_dir, "history_vel.bin", np.dtype("<f4"), sample_slots * tracer_count * 4
    ).reshape(sample_slots, tracer_count, 4)
    initial_tracers = _read_exact(
        run_dir, "initial_tracers.bin", np.dtype("<f4"), tracer_count * 4
    ).reshape(tracer_count, 4)
    final_tracers = _read_exact(
        run_dir, "final_tracers.bin", np.dtype("<f4"), tracer_count * 4
    ).reshape(tracer_count, 4)
    for name, values in (
        ("sample_steps", sample_steps),
        ("history_pos", history_pos),
        ("history_vel", history_vel),
        ("initial_tracers", initial_tracers),
        ("final_tracers", final_tracers),
    ):
        if not np.isfinite(values).all():
            raise AnalysisFailure(f"{name} contains nonfinite values")
    if int(sample_steps.max()) > accepted_steps:
        raise AnalysisFailure("stored sample step exceeds accepted steps")
    if not np.all(np.diff(sample_steps) >= 0):
        raise AnalysisFailure("sample steps are not chronological in an unwrapped ring")

    center = np.asarray(receipt.get("window_center", [0.0, 0.0, 0.0]), dtype=np.float64)
    offset = history_pos[:, :, :3] - center
    radius = np.linalg.norm(offset, axis=2)
    radial_velocity = np.zeros_like(radius)
    nonzero = radius > 0.0
    if bool(nonzero.any()):
        radial_unit = offset[nonzero] / radius[nonzero][:, None]
        radial_velocity[nonzero] = np.sum(radial_unit * history_vel[:, :, :3][nonzero], axis=1)
    alive = history_pos[:, :, 3] > 0.0
    finite = np.isfinite(history_pos).all(axis=2) & np.isfinite(history_vel).all(axis=2)
    valid = alive & finite
    if not valid.any():
        raise AnalysisFailure("no live finite tracers in history")
    configured_extents = np.asarray(receipt.get("extents", []), dtype=np.float64)
    extent_max = float(np.max(configured_extents)) if configured_extents.size else 0.0
    if extent_max <= 0.0:
        raise AnalysisFailure("receipt has no positive configured extent")
    max_radius = float(np.max(radius[valid]))
    domain_ratio = max_radius / extent_max
    domain_status = "BOUNDED" if domain_ratio <= 2.0 else "OUT_OF_DOMAIN"

    initial_valid = initial_tracers[:, 3] > 0.0
    initial_radius = np.linalg.norm(initial_tracers[:, :3] - center, axis=1)
    support = float(initial_radius[initial_valid].max()) if initial_valid.any() else 0.0

    late_cut = LATE_FRACTION * accepted_steps
    late = sample_steps >= late_cut
    if int(late.sum()) < 8:
        raise AnalysisFailure("late window holds fewer than eight samples")

    edges = np.linspace(0.0, U_MAX, BINS + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    du = edges[1] - edges[0]
    r50_series: list[float] = []
    r90_series: list[float] = []
    for slot in range(sample_slots):
        values = radius[slot][valid[slot]]
        if values.size < 2:
            r50_series.append(0.0)
            r90_series.append(0.0)
            continue
        r50_series.append(float(np.median(values)))
        r90_series.append(float(np.percentile(values, 90)))
    slot_profiles: dict[int, np.ndarray] = {}
    slot_ridge_counts: dict[int, int] = {}
    for slot in range(sample_slots):
        values = radius[slot][valid[slot]]
        r50 = r50_series[slot]
        if values.size < 2 or r50 <= 0.0:
            continue
        counts, _ = np.histogram(values / r50, bins=edges)
        sample_profile = counts / float(values.size) / du
        slot_profiles[slot] = sample_profile
        slot_ridge_counts[slot] = len(_ridges(sample_profile, centers))
    late_slots = [slot for slot in slot_profiles if bool(late[slot])]
    if not late_slots:
        raise AnalysisFailure("late window produced no radial profile")
    late_stack = np.stack([slot_profiles[slot] for slot in late_slots], axis=0)
    profile = np.mean(late_stack, axis=0)
    ridges = _ridges(profile, centers)
    if late_stack.shape[0] > 1:
        se_profile = np.std(late_stack, axis=0, ddof=1) / float(np.sqrt(late_stack.shape[0]))
    else:
        se_profile = np.zeros(profile.size, dtype=np.float64)
    for ridge in ridges:
        peak_index = int(ridge.pop("index"))
        saddle_index = int(ridge.pop("saddle_index"))
        spread = float(np.hypot(se_profile[peak_index], se_profile[saddle_index]))
        ridge["z"] = (
            float((ridge["peak"] - float(profile[saddle_index])) / spread)
            if spread > 0.0
            else float("inf")
        )

    final_valid = valid[-1]
    sphericity = _sphericity(final_tracers[final_valid, :3])
    streams = _stream_diagnostic(radius, radial_velocity, valid, sample_steps, late_slots)
    mid_slots = [
        slot
        for slot in sorted(slot_profiles)
        if 0.40 * accepted_steps <= float(sample_steps[slot]) < 0.75 * accepted_steps
    ]
    streams_mid = _stream_diagnostic(radius, radial_velocity, valid, sample_steps, mid_slots)

    r50_late = np.asarray(
        [r50_series[slot] for slot in range(sample_slots) if late[slot]], dtype=np.float64
    )
    r90_late = np.asarray(
        [r90_series[slot] for slot in range(sample_slots) if late[slot]], dtype=np.float64
    )
    concentration = float(np.mean(r90_late / np.maximum(r50_late, 1.0e-30)))
    ridge_counts = np.asarray([slot_ridge_counts[slot] for slot in late_slots], dtype=np.int64)
    instantaneous_ridges = _ridges(slot_profiles[late_slots[-1]], centers)
    for ridge in instantaneous_ridges:
        ridge.pop("index", None)
        ridge.pop("saddle_index", None)
    window_stability: dict[str, Any] = {}
    for name, (low, high) in (
        ("mid", (0.50, 0.75)),
        ("late", (0.75, 0.90)),
        ("final", (0.90, 1.01)),
    ):
        selected = [
            sample_profile
            for slot, sample_profile in slot_profiles.items()
            if low * accepted_steps <= float(sample_steps[slot]) < high * accepted_steps
        ]
        if not selected:
            continue
        window_profile = np.mean(np.stack(selected, axis=0), axis=0)
        window_ridges = _ridges(window_profile, centers)
        window_stability[name] = {
            "samples": len(selected),
            "ridge_count": len(window_ridges),
            "ridge_positions": [round(float(ridge["u"]), 4) for ridge in window_ridges],
        }

    return {
        "run_dir": str(run_dir),
        "ic_index": int(receipt["engine"]["initial_condition"]),
        "ic_name": str(receipt.get("geometry", {}).get("initial_condition", "")),
        "frozen_keys_verified": frozen_checked,
        "accepted_steps": accepted_steps,
        "tracer_count": tracer_count,
        "sample_slots": sample_slots,
        "sample_stride": sample_stride,
        "late_samples": int(late.sum()),
        "initial_support": support,
        "configured_extent_max": extent_max,
        "max_radius": max_radius,
        "domain_ratio": domain_ratio,
        "domain_status": domain_status,
        "initial_live_count": int(receipt["initial_live_count"]),
        "final_live_count": int(receipt["final_live_count"]),
        "initial_total_mass": initial_total_mass,
        "final_total_mass": final_total_mass,
        "relative_mass_error": relative_mass_error,
        "r50_final": r50_series[-1],
        "r90_final": r90_series[-1],
        "r50_late_mean": float(np.mean(r50_late)),
        "r50_late_std": float(np.std(r50_late)),
        "r50_late_min": float(np.min(r50_late)),
        "r50_late_max": float(np.max(r50_late)),
        "r90_late_mean": float(np.mean(r90_late)),
        "concentration_r90_over_r50": concentration,
        "late_slot_ridge_counts": {
            "min": int(ridge_counts.min()),
            "median": float(np.median(ridge_counts)),
            "max": int(ridge_counts.max()),
            "histogram": {
                str(count): int(np.count_nonzero(ridge_counts == count))
                for count in sorted(set(int(value) for value in ridge_counts))
            },
        },
        "instantaneous_ridge_count": len(instantaneous_ridges),
        "instantaneous_ridges": instantaneous_ridges,
        "profile_se_max": float(se_profile.max()),
        "window_stability": window_stability,
        "r50_series": [round(float(value), 6) for value in r50_series],
        "epoch_ridges": _epoch_ridge_series(slot_profiles, centers, sample_steps, r50_series),
        "slot_ridge_series": [
            {
                "step": int(sample_steps[slot]),
                "ridges": [
                    round(float(ridge["u"]), 4) for ridge in _ridges(slot_profiles[slot], centers)
                ],
            }
            for slot in range(sample_slots)
            if slot in slot_profiles
        ],
        "sphericity": sphericity,
        "streams": streams,
        "streams_mid": streams_mid,
        "ridge_count": len(ridges),
        "ridges": ridges,
        "profile_u": centers.tolist(),
        "profile": profile.tolist(),
        "shell_verdict": (
            "SHELL_SUPPORTS" if len(ridges) >= MIN_RIDGES_PER_ARM else "SHELL_DOES_NOT_EMERGE"
        ),
        "scene_shell_verdict": (
            "OUT_OF_DOMAIN"
            if domain_status != "BOUNDED"
            else (
                "SCENE_SHELL_SUPPORTS"
                if len(ridges) >= MIN_RIDGES_PER_ARM
                else "SCENE_SHELL_DOES_NOT_EMERGE"
            )
        ),
    }


def _match_ridges(
    reference: list[dict[str, float]], other: list[dict[str, float]]
) -> dict[str, Any]:
    used: set[int] = set()
    matches: list[dict[str, float]] = []
    for ridge in other:
        best_index = -1
        best_delta = MATCH_TOLERANCE
        for index, target in enumerate(reference):
            if index in used:
                continue
            delta = abs(ridge["u"] - target["u"])
            if delta <= best_delta:
                best_index = index
                best_delta = delta
        if best_index >= 0:
            used.add(best_index)
            matches.append(
                {
                    "u": ridge["u"],
                    "reference_u": reference[best_index]["u"],
                    "delta": best_delta,
                }
            )
    return {"matches": matches, "match_count": len(matches)}


def _is_app_fidelity_summary(arms: list[dict[str, Any]]) -> bool:
    return bool(arms) and all(
        Path(str(arm.get("run_dir", ""))).name in APP_FIDELITY_FROZEN
        for arm in arms
    )


def _is_calibrated_scene_summary(arms: list[dict[str, Any]]) -> bool:
    return bool(arms) and all(
        Path(str(arm.get("run_dir", ""))).name in SCENE_CALIBRATED_FROZEN
        for arm in arms
    )


def _scene_control_summary(
    arms: list[dict[str, Any]], scope: str, reason: str, registered_arms: int
) -> dict[str, Any]:
    ok_arms = [arm for arm in arms if arm.get("status") == "OK"]
    bounded_arms = [arm for arm in ok_arms if arm.get("domain_status") == "BOUNDED"]
    out_of_domain_arms = [
        arm for arm in ok_arms if arm.get("domain_status") == "OUT_OF_DOMAIN"
    ]
    bounded_arms_with_ridges = [
        arm for arm in bounded_arms if arm.get("ridge_count", 0) >= MIN_RIDGES_PER_ARM
    ]
    return {
        "schema": "cassi.trajectory-attractor-summary.v1",
        "prereg": "research/matter_formation/trajectory_general_attractor_prereg.md",
        "scope": scope,
        "verdict": "NOT_DEFINED",
        "reason": reason,
        "registered_arms": registered_arms,
        "qualifying_arms": len(ok_arms),
        "bounded_arms": len(bounded_arms),
        "out_of_domain_arms": len(out_of_domain_arms),
        "bounded_arms_with_ridges": len(bounded_arms_with_ridges),
        "arms": arms,
    }


def summarize(arms: list[dict[str, Any]]) -> dict[str, Any]:
    if _is_app_fidelity_summary(arms):
        return _scene_control_summary(
            arms,
            "app_fidelity_controls",
            "§5 registers app-fidelity controls; it does not register an aggregate mechanism threshold",
            len(APP_FIDELITY_FROZEN),
        )
    if _is_calibrated_scene_summary(arms):
        return _scene_control_summary(
            arms,
            "calibrated_scene_follow_up",
            "§7 registers per-arm scene-fidelity diagnostics; it does not register an aggregate mechanism threshold",
            len(SCENE_CALIBRATED_FROZEN),
        )
    reference = next(
        (
            arm
            for arm in arms
            if arm.get("status") == "OK" and arm.get("ic_index") == REFERENCE_IC
        ),
        None,
    )
    ok_arms = [arm for arm in arms if arm.get("status") == "OK"]
    arms_with_ridges = [arm for arm in ok_arms if arm["ridge_count"] >= MIN_RIDGES_PER_ARM]
    matching: dict[str, Any] = {}
    matched_arms = 0
    if reference is not None:
        for arm in ok_arms:
            if arm is reference:
                continue
            result = _match_ridges(reference["ridges"], arm["ridges"])
            matching[str(arm["ic_index"])] = result
            if result["match_count"] >= 2:
                matched_arms += 1

    if len(ok_arms) < MIN_QUALIFYING_ARMS:
        verdict = "INCONCLUSIVE"
        reason = f"qualifying arms={len(ok_arms)} below {MIN_QUALIFYING_ARMS}"
    elif reference is None:
        verdict = "INCONCLUSIVE"
        reason = "reference arm missing"
    elif len(arms_with_ridges) <= DOES_NOT_EMERGE_MAX_ARMS_WITH_RIDGES:
        verdict = "DOES NOT EMERGE"
        reason = (
            f"arms with ridges={len(arms_with_ridges)} <= "
            f"{DOES_NOT_EMERGE_MAX_ARMS_WITH_RIDGES}"
        )
    elif len(arms_with_ridges) < SUPPORT_MIN_ARMS_WITH_RIDGES:
        verdict = "INCONCLUSIVE"
        reason = (
            f"arms with ridges={len(arms_with_ridges)} between "
            f"{DOES_NOT_EMERGE_MAX_ARMS_WITH_RIDGES + 1} and {SUPPORT_MIN_ARMS_WITH_RIDGES - 1}"
        )
    elif matched_arms >= SUPPORT_MIN_MATCHED_ARMS:
        verdict = "SUPPORTS"
        reason = (
            f"arms with ridges={len(arms_with_ridges)}, matched arms={matched_arms}"
        )
    else:
        verdict = "INCONCLUSIVE"
        reason = (
            f"arms with ridges={len(arms_with_ridges)} but matched arms={matched_arms} "
            f"below {SUPPORT_MIN_MATCHED_ARMS}"
        )

    return {
        "schema": "cassi.trajectory-attractor-summary.v1",
        "prereg": "research/matter_formation/trajectory_general_attractor_prereg.md",
        "verdict": verdict,
        "reason": reason,
        "qualifying_arms": len(ok_arms),
        "arms_with_ridges": len(arms_with_ridges),
        "matched_arms": matched_arms,
        "reference_ic": REFERENCE_IC,
        "arms": arms,
        "matching": matching,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        type=Path,
        action="append",
        default=None,
        help="arm directory; repeatable (default: the eight registered arms)",
    )
    parser.add_argument(
        "--allow-unregistered",
        action="store_true",
        help="analyze a directory without a registered frozen configuration (exploratory only)",
    )
    parser.add_argument("--out", type=Path, default=DIAG_ROOT / "attractor_summary.json")
    args = parser.parse_args(argv)
    run_dirs = args.run if args.run else [_arm_dir(ic) for ic in DEFAULT_ICS]

    arms: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        if not (run_dir / "receipt.json").is_file():
            arms.append({"run_dir": str(run_dir), "status": "MISSING"})
            print(f"{run_dir}: MISSING")
            continue
        try:
            arm = analyze_arm(run_dir, strict=not args.allow_unregistered)
        except AnalysisFailure as exc:
            arms.append({"run_dir": str(run_dir), "status": "FAIL", "error": str(exc)})
            print(f"{run_dir}: FAIL — {exc}")
            continue
        arm["status"] = "OK"
        (run_dir / "analysis.json").write_text(
            json.dumps(_json_safe(arm), indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        ridge_text = ", ".join(f"{ridge['u']:.3f}" for ridge in arm["ridges"])
        envelope = arm["late_slot_ridge_counts"]
        print(
            f"{run_dir}: ic={arm['ic_index']} {arm['ic_name']} "
            f"frozen_keys={arm['frozen_keys_verified']} ridges={arm['ridge_count']} "
            f"[{ridge_text}] b/a={arm['sphericity']['axis_ba']:.3f} "
            f"c/a={arm['sphericity']['axis_ca']:.3f} r90/r50={arm['concentration_r90_over_r50']:.2f} "
            f"r50_std={arm['r50_late_std']:.2f} inst_ridges={arm['instantaneous_ridge_count']} "
            f"slot_ridges={envelope['min']}/{envelope['median']:.0f}/{envelope['max']} "
            f"domain={arm['domain_status']} ratio={arm['domain_ratio']:.2f} "
            f"{arm['shell_verdict']}"
        )
        arms.append(arm)

    summary = summarize(arms)
    args.out.write_text(
        json.dumps(_json_safe(summary), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    if summary.get("scope") in {"app_fidelity_controls", "calibrated_scene_follow_up"}:
        print(
            f"\nVERDICT: {summary['verdict']} — {summary['reason']} "
            f"(qualifying={summary['qualifying_arms']}/"
            f"{summary['registered_arms']}, bounded={summary['bounded_arms']}, "
            f"out_of_domain={summary['out_of_domain_arms']}, "
            f"bounded_ridges={summary['bounded_arms_with_ridges']})"
        )
    else:
        print(
            f"\nVERDICT: {summary['verdict']} — {summary['reason']} "
            f"(qualifying={summary['qualifying_arms']}, ridges={summary['arms_with_ridges']}, "
            f"matched={summary['matched_arms']})"
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
