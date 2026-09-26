"""Hive-native temporal residual-authority experiment.

Every measurement is made by the root or an independent member of one living
research organism.  The actors receive disjoint development arms, challenge the
same candidate lessons through their own fields, and admit only quorum-supported
knowledge to their shared Hive.  There is intentionally no isolated execution
mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

import cassi_full_observable_invention as legacy
from cassi_morphology_observables import MORPHOLOGY_ATOMS
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated
from cassi_research_organism import ResearchOrganism

SCHEMA = "cassifi.hive-temporal-residual-authority.v2"
SLICE_SCHEMA = "cassifi.hive-temporal-residual-authority-slice.v2"
EXPERIMENT_ID = "temporal-residual-authority-v2"
LABORATORY_ID = "trajectory-residual-authority"
PRIOR_FINDING = "CassiFI/_diag/morphology-residual-authority-v1.json"
FIT_FRACTION = 0.60
LAGS = (1, 2, 4, 8)
RIDGE = 1e-10
SPECTRUM_RELATIVE_EIGENVALUE_TOLERANCE = 1e-10
BASE_ATOMS = tuple(atom for atom in SEED_ATOMS if atom not in MORPHOLOGY_ATOMS)
PRESENT_ATOMS = (*BASE_ATOMS, *MORPHOLOGY_ATOMS)
ANALYSIS_SOURCES = (
    "CassiFI/cassi_temporal_residual_authority.py",
    "CassiFI/cassi_morphology_residual_authority.py",
    "CassiFI/cassi_morphology_operator_invention.py",
    "CassiFI/cassi_morphology_observables.py",
    "CassiFI/cassi_full_observable_invention.py",
    "CassiFI/cassi_research_organism.py",
)


class TemporalAuthorityError(RuntimeError):
    """Raised when the integrated temporal experiment cannot be measured safely."""


@dataclass(frozen=True, slots=True)
class TemporalChannel:
    name: str
    atom: str
    frame: str
    family: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "atom": self.atom,
            "frame": self.frame,
            "family": self.family,
        }


CHANNELS = (
    TemporalChannel("coherence-flow", "q", "flow", "dynamic"),
    TemporalChannel("speed-flow", "speed", "flow", "dynamic"),
    TemporalChannel("radial-transport", "radial_speed", "radial", "dynamic"),
    TemporalChannel("transverse-transport", "transverse_speed", "transverse", "dynamic"),
    TemporalChannel("field-gradient", "field_energy", "coherence_gradient", "dynamic"),
    TemporalChannel("density-flow", "local_density", "flow", "dynamic"),
    TemporalChannel("density-gradient", "local_density", "density_gradient", "dynamic"),
    TemporalChannel("enclosed-mass-radial", "enclosed_mass", "radial", "dynamic"),
    TemporalChannel("divergence-flow", "divergence", "flow", "dynamic"),
    TemporalChannel("shear-normal", "shear", "normal", "dynamic"),
    TemporalChannel("compactness-radial", "morphology_compactness", "radial", "morphology"),
    TemporalChannel("radial-spread-radial", "morphology_radial_spread", "radial", "morphology"),
    TemporalChannel("shell-tangentiality-flow", "morphology_shell_tangentiality", "flow", "morphology"),
    TemporalChannel("counterflow-flow", "morphology_counterflow", "flow", "morphology"),
    TemporalChannel("anisotropy-normal", "morphology_anisotropy", "normal", "morphology"),
    TemporalChannel("planarity-normal", "morphology_planarity", "normal", "morphology"),
)

LESSON_STATEMENTS = {
    "trajectory-history-authority": (
        "Identity-aligned trajectory history carries stable acceleration authority "
        "beyond the complete present snapshot."
    ),
    "regime-history-authority": (
        "Past population state carries residual regime authority, but tracer identity "
        "does not materially strengthen it."
    ),
    "no-stable-history-authority": (
        "The disclosed lag and derivative-equivalent history carries no stable "
        "held-out authority beyond the complete present snapshot."
    ),
}


@dataclass(slots=True)
class _BaseContext:
    train_design: np.ndarray
    validation_design: np.ndarray
    train_target: np.ndarray
    validation_target: np.ndarray
    inverse_gram: np.ndarray
    train_residual: np.ndarray
    validation_prediction: np.ndarray
    baseline_nrmse: float

    def project(self, train_block: np.ndarray, validation_block: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        coefficients = self.inverse_gram @ (self.train_design.T @ train_block)
        return (
            train_block - self.train_design @ coefficients,
            validation_block - self.validation_design @ coefficients,
        )


@dataclass(slots=True)
class _ArmAnalysis:
    receipt: dict[str, Any]
    history_gram: np.ndarray
    history_rows: int


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_manifest(
    workspace: Path,
    organism_sources: Sequence[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    relative_paths = sorted(set(ANALYSIS_SOURCES) | set(organism_sources))
    for relative in relative_paths:
        path = workspace / relative
        if not path.is_file():
            raise TemporalAuthorityError(f"analysis source is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _load_prior_finding(workspace: Path) -> dict[str, Any]:
    path = workspace / PRIOR_FINDING
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TemporalAuthorityError("prior morphology authority finding is unavailable") from exc
    if (
        value.get("schema") != "cassifi.morphology-residual-authority.v1"
        or value.get("arm_count") != 16
        or value.get("duplicate_identity_control", {}).get("status") != "PASS"
        or value.get("injected_compactness_control", {}).get("status") != "PASS"
    ):
        raise TemporalAuthorityError("prior morphology authority finding is not admissible")
    return {
        "path": PRIOR_FINDING,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "arm_count": int(value["arm_count"]),
        "mean_combined_fractional_rmse_reduction": float(
            value["mean_combined_fractional_rmse_reduction"]
        ),
        "conditional_rank": int(value["conditional_morphology_spectrum"]["rank"]),
        "conclusion": (
            "present-snapshot morphology was conditionally full-rank but did not "
            "improve combined chronological validation"
        ),
    }


def _rms_scale(values: np.ndarray) -> float:
    scale = float(np.sqrt(np.mean(np.asarray(values, dtype=np.float64) ** 2)))
    return scale if np.isfinite(scale) and scale > 1e-12 else 0.0


def _scaled(values: np.ndarray, scale: float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    return np.zeros_like(array) if scale == 0.0 else array / scale


def _present_scales(
    bundle: legacy.FeatureBundle,
    train_rows: np.ndarray,
    atoms: Iterable[str],
) -> dict[str, float]:
    return {
        atom: _rms_scale(np.asarray(bundle.atoms[atom])[train_rows])
        for atom in atoms
    }


def _present_matrix(
    bundle: legacy.FeatureBundle,
    rows: np.ndarray,
    atoms: Sequence[str],
    scales: Mapping[str, float],
) -> np.ndarray:
    columns: list[np.ndarray] = []
    for atom in atoms:
        scalar = _scaled(np.asarray(bundle.atoms[atom])[rows], scales[atom])
        for frame in legacy.FRAMES:
            columns.append(np.asarray(bundle.frames[frame], dtype=np.float64)[rows] * scalar[:, None])
    return np.concatenate(columns, axis=1)


def _history_scales(
    bundle: legacy.FeatureBundle,
    past_rows: Mapping[int, np.ndarray],
    channels: Sequence[TemporalChannel],
) -> dict[tuple[int, str], float]:
    return {
        (lag, atom): _rms_scale(np.asarray(bundle.atoms[atom])[past_rows[lag]])
        for lag in LAGS
        for atom in {channel.atom for channel in channels}
    }


def _history_matrix(
    bundle: legacy.FeatureBundle,
    past_rows: Mapping[int, np.ndarray],
    channels: Sequence[TemporalChannel],
    scales: Mapping[tuple[int, str], float],
) -> np.ndarray:
    columns: list[np.ndarray] = []
    for lag in LAGS:
        rows = past_rows[lag]
        for channel in channels:
            scalar = _scaled(
                np.asarray(bundle.atoms[channel.atom])[rows],
                scales[(lag, channel.atom)],
            )
            columns.append(
                np.asarray(bundle.frames[channel.frame], dtype=np.float64)[rows]
                * scalar[:, None]
            )
    return np.concatenate(columns, axis=1)


def _current_channel_matrix(
    bundle: legacy.FeatureBundle,
    rows: np.ndarray,
    scales: Mapping[str, float],
) -> np.ndarray:
    return np.concatenate(
        [
            np.asarray(bundle.frames[channel.frame], dtype=np.float64)[rows]
            * _scaled(np.asarray(bundle.atoms[channel.atom])[rows], scales[channel.atom])[:, None]
            for channel in CHANNELS
        ],
        axis=1,
    )


def _present_channel_indices(atoms: Sequence[str]) -> np.ndarray:
    atom_positions = {atom: index for index, atom in enumerate(atoms)}
    frame_positions = {frame: index for index, frame in enumerate(legacy.FRAMES)}
    indices: list[int] = []
    for channel in CHANNELS:
        try:
            atom_index = atom_positions[channel.atom]
            frame_index = frame_positions[channel.frame]
        except KeyError as exc:
            raise TemporalAuthorityError(
                f"current channel is absent from the present design: {channel.name}"
            ) from exc
        start = (atom_index * len(legacy.FRAMES) + frame_index) * 3
        indices.extend(range(start, start + 3))
    return np.asarray(indices, dtype=np.int64)


def _ridge_inverse(design: np.ndarray) -> np.ndarray:
    gram = design.T @ design
    ridge = RIDGE * max(1.0, float(np.trace(gram)) / max(1, gram.shape[0]))
    return np.linalg.inv(gram + ridge * np.eye(gram.shape[0], dtype=np.float64))


def _ridge_fit(design: np.ndarray, target: np.ndarray) -> np.ndarray:
    gram = design.T @ design
    ridge = RIDGE * max(1.0, float(np.trace(gram)) / max(1, gram.shape[0]))
    return np.linalg.solve(
        gram + ridge * np.eye(gram.shape[0], dtype=np.float64),
        design.T @ target,
    )


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    target_rms = _rms_scale(target)
    if target_rms == 0.0:
        raise TemporalAuthorityError("authority target has zero RMS")
    return float(np.sqrt(np.mean((prediction - target) ** 2)) / target_rms)


def _base_context(
    train_design: np.ndarray,
    validation_design: np.ndarray,
    train_target: np.ndarray,
    validation_target: np.ndarray,
    *,
    inverse_gram: np.ndarray | None = None,
) -> _BaseContext:
    inverse = _ridge_inverse(train_design) if inverse_gram is None else inverse_gram
    coefficients = inverse @ (train_design.T @ train_target)
    train_prediction = train_design @ coefficients
    validation_prediction = validation_design @ coefficients
    return _BaseContext(
        train_design=train_design,
        validation_design=validation_design,
        train_target=train_target,
        validation_target=validation_target,
        inverse_gram=inverse,
        train_residual=train_target - train_prediction,
        validation_prediction=validation_prediction,
        baseline_nrmse=_nrmse(validation_prediction, validation_target),
    )


def _reading_from_residual(
    context: _BaseContext,
    train_residual_block: np.ndarray,
    validation_residual_block: np.ndarray,
) -> dict[str, float]:
    coefficients = _ridge_fit(train_residual_block, context.train_residual)
    enriched_prediction = context.validation_prediction + validation_residual_block @ coefficients
    enriched = _nrmse(enriched_prediction, context.validation_target)
    return {
        "baseline_nrmse": context.baseline_nrmse,
        "enriched_nrmse": enriched,
        "fractional_rmse_reduction": float(1.0 - enriched / context.baseline_nrmse),
    }


def _spectrum_from_gram(gram: np.ndarray, rows: int) -> dict[str, Any]:
    eigenvalues = np.maximum(
        np.linalg.eigvalsh(0.5 * (gram + gram.T)),
        0.0,
    )[::-1]
    lambda_max = float(eigenvalues[0]) if len(eigenvalues) else 0.0
    eigenvalue_tolerance = (
        SPECTRUM_RELATIVE_EIGENVALUE_TOLERANCE * lambda_max
    )
    rank = int(np.count_nonzero(eigenvalues > eigenvalue_tolerance))
    singular = np.sqrt(eigenvalues)
    return {
        "shape": [int(rows), int(gram.shape[0])],
        "rank": rank,
        "relative_eigenvalue_tolerance": SPECTRUM_RELATIVE_EIGENVALUE_TOLERANCE,
        "eigenvalue_tolerance": eigenvalue_tolerance,
        "sigma_max": float(singular[0]) if len(singular) else 0.0,
        "sigma_min_nonzero": float(singular[rank - 1]) if rank else 0.0,
    }


def _trajectory_rows(
    root: Path,
    bundle: legacy.FeatureBundle,
) -> tuple[np.ndarray, np.ndarray, float, list[dict[str, Any]]]:
    try:
        receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TemporalAuthorityError(f"trajectory receipt is unreadable: {root}") from exc
    slots = int(receipt["sample_slots"])
    tracers = int(receipt["tracer_count"])
    position = np.memmap(
        root / "history_pos.bin",
        mode="r",
        dtype="<f4",
        shape=(slots, tracers, 4),
    )
    center = np.asarray(receipt["engine"]["window_center"], dtype=np.float64)
    tracer_rows: list[np.ndarray] = []
    middle_rows: list[np.ndarray] = []
    for slot in range(1, slots - 1):
        raw_position = np.asarray(position[slot, :, :3], dtype=np.float64) - center
        radius = np.linalg.norm(raw_position, axis=1)
        live = (np.asarray(position[slot, :, 3]) > 0.0) & (radius > legacy.MINIMUM_RADIUS)
        live_indices = np.flatnonzero(live)
        selected = live_indices[(live_indices % legacy.TRACER_MODULUS) == 0]
        tracer_rows.append(selected.astype(np.int32, copy=False))
        middle_rows.append(np.full(len(selected), slot - 1, dtype=np.int32))
    tracers_flat = np.concatenate(tracer_rows)
    middle_flat = np.concatenate(middle_rows)
    if not np.array_equal(middle_flat, bundle.middle_index) or len(tracers_flat) != len(bundle.target):
        raise TemporalAuthorityError(f"trajectory identity rows diverge from feature rows: {root}")
    steps = np.fromfile(root / "sample_steps.bin", dtype="<u4").astype(np.float64)
    if len(steps) != slots or not np.all(np.diff(steps) > 0.0):
        raise TemporalAuthorityError(f"trajectory clock is invalid: {root}")
    source_manifest = []
    for name in legacy._TRAJECTORY_FILES:
        path = root / name
        source_manifest.append(
            {
                "name": name,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return tracers_flat, steps, float(receipt["dt"]), source_manifest


def _align_trajectory_rows(
    middle_index: np.ndarray,
    tracer_index: np.ndarray,
    lags: Sequence[int] = LAGS,
) -> tuple[np.ndarray, dict[int, np.ndarray]]:
    """Return current and same-tracer past row indices for every requested lag."""
    middle = np.asarray(middle_index, dtype=np.int64)
    tracer = np.asarray(tracer_index, dtype=np.int64)
    if middle.ndim != 1 or tracer.shape != middle.shape:
        raise TemporalAuthorityError("trajectory identity arrays must be aligned vectors")
    normalized_lags = tuple(int(lag) for lag in lags)
    if not normalized_lags or any(lag <= 0 for lag in normalized_lags):
        raise TemporalAuthorityError("trajectory lags must be positive")
    lookup: dict[tuple[int, int], int] = {}
    for row, key in enumerate(zip(middle.tolist(), tracer.tolist())):
        if key in lookup:
            raise TemporalAuthorityError("trajectory identity key is duplicated")
        lookup[key] = row
    current: list[int] = []
    past: dict[int, list[int]] = {lag: [] for lag in normalized_lags}
    for row, (slot, tracer_id) in enumerate(zip(middle.tolist(), tracer.tolist())):
        candidates = {lag: lookup.get((slot - lag, tracer_id)) for lag in normalized_lags}
        if all(candidate is not None for candidate in candidates.values()):
            current.append(row)
            for lag, candidate in candidates.items():
                assert candidate is not None
                past[lag].append(candidate)
    if not current:
        raise TemporalAuthorityError("no trajectories survive every requested lag")
    return (
        np.asarray(current, dtype=np.int64),
        {lag: np.asarray(rows, dtype=np.int64) for lag, rows in past.items()},
    )


def _break_trajectory_identity(
    current_rows: np.ndarray,
    past_rows: Mapping[int, np.ndarray],
    middle_index: np.ndarray,
) -> tuple[dict[int, np.ndarray], float]:
    """Cyclically exchange past tracers only within the same current time slot."""
    current_middle = np.asarray(middle_index, dtype=np.int64)[current_rows]
    broken = {lag: np.asarray(rows, dtype=np.int64).copy() for lag, rows in past_rows.items()}
    changed = 0
    total = 0
    for slot in np.unique(current_middle):
        positions = np.flatnonzero(current_middle == slot)
        if len(positions) < 2:
            continue
        for lag in broken:
            original = broken[lag][positions].copy()
            broken[lag][positions] = np.roll(original, 1)
            changed += int(np.count_nonzero(broken[lag][positions] != original))
            total += len(positions)
    if total == 0:
        raise TemporalAuthorityError("trajectory identity break has no exchangeable rows")
    return broken, float(changed / total)


def _column_indices(*, family: str | None = None, lag: int | None = None, channel_name: str | None = None) -> np.ndarray:
    indices: list[int] = []
    for lag_index, lag_value in enumerate(LAGS):
        for channel_index, channel in enumerate(CHANNELS):
            if family is not None and channel.family != family:
                continue
            if lag is not None and lag_value != lag:
                continue
            if channel_name is not None and channel.name != channel_name:
                continue
            start = (lag_index * len(CHANNELS) + channel_index) * 3
            indices.extend(range(start, start + 3))
    return np.asarray(indices, dtype=np.int64)


def _analyze_arm(
    root: Path,
    bundle: legacy.FeatureBundle,
) -> _ArmAnalysis:
    tracer_index, steps, dt, source_manifest = _trajectory_rows(root, bundle)
    current_rows, past_rows = _align_trajectory_rows(bundle.middle_index, tracer_index)
    broken_past, identity_mismatch = _break_trajectory_identity(
        current_rows,
        past_rows,
        bundle.middle_index,
    )
    count = int(bundle.middle_index.max()) + 1
    cutoff = int(FIT_FRACTION * count)
    train_selector = np.asarray(bundle.middle_index)[current_rows] < cutoff
    validation_selector = ~train_selector
    if np.count_nonzero(train_selector) < 64 or np.count_nonzero(validation_selector) < 64:
        raise TemporalAuthorityError(f"trajectory split is too small: {root}")
    train_rows = current_rows[train_selector]
    validation_rows = current_rows[validation_selector]
    train_past = {lag: rows[train_selector] for lag, rows in past_rows.items()}
    validation_past = {lag: rows[validation_selector] for lag, rows in past_rows.items()}
    train_broken = {lag: rows[train_selector] for lag, rows in broken_past.items()}
    validation_broken = {lag: rows[validation_selector] for lag, rows in broken_past.items()}

    present_scales = _present_scales(bundle, train_rows, PRESENT_ATOMS)
    strict_train = _present_matrix(bundle, train_rows, PRESENT_ATOMS, present_scales)
    strict_validation = _present_matrix(bundle, validation_rows, PRESENT_ATOMS, present_scales)
    dynamic_train = _present_matrix(bundle, train_rows, BASE_ATOMS, present_scales)
    dynamic_validation = _present_matrix(bundle, validation_rows, BASE_ATOMS, present_scales)
    train_target = np.asarray(bundle.target, dtype=np.float64)[train_rows]
    validation_target = np.asarray(bundle.target, dtype=np.float64)[validation_rows]
    strict_context = _base_context(
        strict_train,
        strict_validation,
        train_target,
        validation_target,
    )
    dynamic_context = _base_context(
        dynamic_train,
        dynamic_validation,
        train_target,
        validation_target,
    )

    history_scales = _history_scales(bundle, train_past, CHANNELS)
    history_train = _history_matrix(bundle, train_past, CHANNELS, history_scales)
    history_validation = _history_matrix(bundle, validation_past, CHANNELS, history_scales)
    broken_train = _history_matrix(bundle, train_broken, CHANNELS, history_scales)
    broken_validation = _history_matrix(bundle, validation_broken, CHANNELS, history_scales)
    strict_history_train, strict_history_validation = strict_context.project(
        history_train,
        history_validation,
    )
    dynamic_history_train, dynamic_history_validation = dynamic_context.project(
        history_train,
        history_validation,
    )
    broken_residual_train, broken_residual_validation = strict_context.project(
        broken_train,
        broken_validation,
    )

    all_indices = np.arange(history_train.shape[1], dtype=np.int64)
    dynamic_indices = _column_indices(family="dynamic")
    morphology_indices = _column_indices(family="morphology")

    def strict_read(indices: np.ndarray) -> dict[str, float]:
        return _reading_from_residual(
            strict_context,
            strict_history_train[:, indices],
            strict_history_validation[:, indices],
        )

    strict_all = strict_read(all_indices)
    strict_dynamic = strict_read(dynamic_indices)
    strict_morphology = strict_read(morphology_indices)
    broken_reading = _reading_from_residual(
        strict_context,
        broken_residual_train,
        broken_residual_validation,
    )
    dynamic_conditioning = _reading_from_residual(
        dynamic_context,
        dynamic_history_train,
        dynamic_history_validation,
    )
    by_lag = {
        str(lag): strict_read(_column_indices(lag=lag))
        for lag in LAGS
    }
    by_channel = {
        channel.name: strict_read(_column_indices(channel_name=channel.name))
        for channel in CHANNELS
    }

    current_train = _current_channel_matrix(bundle, train_rows, present_scales)
    current_validation = _current_channel_matrix(bundle, validation_rows, present_scales)
    represented_indices = _present_channel_indices(PRESENT_ATOMS)
    represented_train = strict_train[:, represented_indices]
    represented_validation = strict_validation[:, represented_indices]
    current_denominator = math.hypot(
        float(np.linalg.norm(current_train)),
        float(np.linalg.norm(current_validation)),
    )
    duplicate_current_ratio = (
        0.0
        if current_denominator <= 1e-12
        else math.hypot(
            float(np.linalg.norm(current_train - represented_train)),
            float(np.linalg.norm(current_validation - represented_validation)),
        )
        / current_denominator
    )
    current_residual_train, current_residual_validation = strict_context.project(
        current_train,
        current_validation,
    )
    ridge_projection_ratio = (
        0.0
        if current_denominator <= 1e-12
        else math.hypot(
            float(np.linalg.norm(current_residual_train)),
            float(np.linalg.norm(current_residual_validation)),
        )
        / current_denominator
    )

    firing_indices = _column_indices(lag=LAGS[0], channel_name=CHANNELS[0].name)
    firing_train = strict_history_train[:, firing_indices]
    firing_validation = strict_history_validation[:, firing_indices]
    firing_rms = _rms_scale(firing_train)
    if firing_rms == 0.0:
        raise TemporalAuthorityError(f"lag residual firing direction is degenerate: {root}")
    gain = 0.75 * _rms_scale(train_target) / firing_rms
    injected_context = _base_context(
        strict_train,
        strict_validation,
        train_target + gain * firing_train,
        validation_target + gain * firing_validation,
        inverse_gram=strict_context.inverse_gram,
    )
    injected = _reading_from_residual(
        injected_context,
        firing_train,
        firing_validation,
    )

    identity_denominator = float(
        np.linalg.norm(strict_history_train) + np.linalg.norm(broken_residual_train)
    )
    identity_separation = (
        0.0
        if identity_denominator <= 1e-12
        else float(
            np.linalg.norm(strict_history_train - broken_residual_train)
            / identity_denominator
        )
    )
    physical_lags = {
        str(lag): float(
            np.median(
                (
                    steps[np.asarray(bundle.middle_index)[current_rows] + 1]
                    - steps[np.asarray(bundle.middle_index)[past_rows[lag]] + 1]
                )
                * dt
            )
        )
        for lag in LAGS
    }
    arm_receipt = {
        "arm_id": bundle.arm_id,
        "source_root": str(root),
        "source_summary": dict(bundle.source_summary),
        "source_manifest": source_manifest,
        "samples": {
            "lag_valid": int(len(current_rows)),
            "train": int(len(train_rows)),
            "validation": int(len(validation_rows)),
            "chronological_cutoff": cutoff,
        },
        "physical_lag_by_slot": physical_lags,
        "strict_present_conditioning": {
            "all_history": strict_all,
            "dynamic_history": strict_dynamic,
            "morphology_history": strict_morphology,
            "identity_broken_history": broken_reading,
            "by_lag": by_lag,
            "by_channel": by_channel,
        },
        "dynamic_present_conditioning": {
            "all_history": dynamic_conditioning,
        },
        "controls": {
            "current_duplicate_residual_ratio": duplicate_current_ratio,
            "current_ridge_projection_residual_ratio": ridge_projection_ratio,
            "injected_lag_residual": injected,
            "injection_gain": gain,
            "identity_break_mismatch_fraction": identity_mismatch,
            "identity_break_residual_separation": identity_separation,
        },
    }
    return _ArmAnalysis(
        receipt=arm_receipt,
        history_gram=strict_history_train.T @ strict_history_train,
        history_rows=len(strict_history_train),
    )


def _mean(values: Iterable[float]) -> float:
    rows = [float(value) for value in values]
    if not rows:
        raise TemporalAuthorityError("cannot summarize an empty measurement")
    return float(np.mean(rows))


def _summarize_arms(per_arm: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    arms = list(per_arm.values())

    def reduction(arm: Mapping[str, Any], key: str) -> float:
        return float(
            arm["strict_present_conditioning"][key]["fractional_rmse_reduction"]
        )

    all_values = [reduction(arm, "all_history") for arm in arms]
    broken_values = [reduction(arm, "identity_broken_history") for arm in arms]
    dynamic_values = [reduction(arm, "dynamic_history") for arm in arms]
    morphology_values = [reduction(arm, "morphology_history") for arm in arms]
    dynamic_conditioned = [
        float(
            arm["dynamic_present_conditioning"]["all_history"][
                "fractional_rmse_reduction"
            ]
        )
        for arm in arms
    ]
    return {
        "arm_count": len(arms),
        "mean_all_history_fractional_rmse_reduction": _mean(all_values),
        "mean_dynamic_history_fractional_rmse_reduction": _mean(dynamic_values),
        "mean_morphology_history_fractional_rmse_reduction": _mean(morphology_values),
        "mean_dynamic_conditioned_fractional_rmse_reduction": _mean(dynamic_conditioned),
        "mean_identity_broken_fractional_rmse_reduction": _mean(broken_values),
        "mean_identity_advantage": _mean(
            aligned - broken
            for aligned, broken in zip(all_values, broken_values)
        ),
        "positive_arm_count": int(sum(value > 0.0 for value in all_values)),
        "positive_arm_fraction": float(np.mean(np.asarray(all_values) > 0.0)),
        "mean_by_lag": {
            str(lag): _mean(
                float(
                    arm["strict_present_conditioning"]["by_lag"][str(lag)][
                        "fractional_rmse_reduction"
                    ]
                )
                for arm in arms
            )
            for lag in LAGS
        },
        "mean_by_channel": {
            channel.name: _mean(
                float(
                    arm["strict_present_conditioning"]["by_channel"][channel.name][
                        "fractional_rmse_reduction"
                    ]
                )
                for arm in arms
            )
            for channel in CHANNELS
        },
    }


def _lesson_scores(summary: Mapping[str, Any], *, controls_passed: bool) -> dict[str, float]:
    if not controls_passed:
        return {
            "trajectory-history-authority": 0.0,
            "regime-history-authority": 0.0,
            "no-stable-history-authority": 1.0,
        }
    effect = float(
        np.clip(
            max(float(summary["mean_all_history_fractional_rmse_reduction"]), 0.0)
            / 0.02,
            0.0,
            1.0,
        )
    )
    positive = float(np.clip(summary["positive_arm_fraction"], 0.0, 1.0))
    identity = float(
        np.clip(max(float(summary["mean_identity_advantage"]), 0.0) / 0.01, 0.0, 1.0)
    )
    return {
        "trajectory-history-authority": float(
            np.clip(0.45 * effect + 0.25 * positive + 0.30 * identity, 0.0, 1.0)
        ),
        "regime-history-authority": float(
            np.clip(0.55 * effect + 0.25 * positive + 0.20 * (1.0 - identity), 0.0, 1.0)
        ),
        "no-stable-history-authority": float(
            np.clip(0.65 * (1.0 - effect) + 0.35 * (1.0 - positive), 0.0, 1.0)
        ),
    }


def _scan_active_slice(
    workspace: Path,
    *,
    actor: str,
    roots: Sequence[str],
    prior: Mapping[str, Any],
    analysis_sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not roots:
        raise TemporalAuthorityError(f"hive actor has no assigned arms: {actor}")
    per_arm: dict[str, dict[str, Any]] = {}
    aggregate_gram = np.zeros((len(LAGS) * len(CHANNELS) * 3,) * 2, dtype=np.float64)
    aggregate_rows = 0
    for relative in roots:
        root = (workspace / relative).resolve(strict=True)
        bundle = legacy._load_bundle(str(root))
        missing = set(PRESENT_ATOMS) - set(bundle.atoms)
        if missing:
            raise TemporalAuthorityError(
                f"morphology activation omitted present atoms for {relative}: {sorted(missing)}"
            )
        analyzed = _analyze_arm(root, bundle)
        if analyzed.receipt["arm_id"] in per_arm:
            raise TemporalAuthorityError("development arm identities collide")
        per_arm[analyzed.receipt["arm_id"]] = analyzed.receipt
        aggregate_gram += analyzed.history_gram
        aggregate_rows += analyzed.history_rows
    summary = _summarize_arms(per_arm)
    spectrum = _spectrum_from_gram(aggregate_gram, aggregate_rows)
    duplicate_gram = np.block(
        [[aggregate_gram, aggregate_gram], [aggregate_gram, aggregate_gram]]
    )
    duplicate_spectrum = _spectrum_from_gram(duplicate_gram, aggregate_rows)
    max_current_duplicate = max(
        float(arm["controls"]["current_duplicate_residual_ratio"])
        for arm in per_arm.values()
    )
    mean_injected = _mean(
        float(
            arm["controls"]["injected_lag_residual"][
                "fractional_rmse_reduction"
            ]
        )
        for arm in per_arm.values()
    )
    min_identity_mismatch = min(
        float(arm["controls"]["identity_break_mismatch_fraction"])
        for arm in per_arm.values()
    )
    min_identity_separation = min(
        float(arm["controls"]["identity_break_residual_separation"])
        for arm in per_arm.values()
    )
    controls = {
        "current_duplicate": {
            "status": "PASS" if max_current_duplicate <= 1e-12 else "FAIL",
            "maximum_representation_mismatch_ratio": max_current_duplicate,
            "bound": 1e-12,
        },
        "duplicate_history_rank": {
            "status": "PASS" if duplicate_spectrum["rank"] == spectrum["rank"] else "FAIL",
            "rank": duplicate_spectrum["rank"],
            "reference_rank": spectrum["rank"],
        },
        "injected_lag_residual": {
            "status": "PASS" if mean_injected > 0.25 else "FAIL",
            "mean_fractional_rmse_reduction": mean_injected,
            "bound": 0.25,
        },
        "identity_break_fired": {
            "status": (
                "PASS"
                if min_identity_mismatch >= 0.99 and min_identity_separation > 1e-3
                else "FAIL"
            ),
            "minimum_mismatch_fraction": min_identity_mismatch,
            "minimum_residual_separation": min_identity_separation,
        },
    }
    controls_passed = all(row["status"] == "PASS" for row in controls.values())
    result = {
        "schema": SLICE_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "actor": actor,
        "scope": "disjoint development-only chronological Hive evidence; no hidden holdout",
        "assigned_roots": list(roots),
        "prior_finding": dict(prior),
        "analysis_sources": [dict(row) for row in analysis_sources],
        "lags": list(LAGS),
        "channels": [channel.as_dict() for channel in CHANNELS],
        "present_conditioning_atoms": list(PRESENT_ATOMS),
        "present_frames": list(legacy.FRAMES),
        "temporal_representation": (
            "past channel vectors conditioned on their complete present-snapshot span; "
            "the residual span is finite-difference/trajectory-derivative equivalent"
        ),
        "per_arm": per_arm,
        "summary": summary,
        "conditional_history_spectrum": spectrum,
        "controls": controls,
        "controls_passed": controls_passed,
    }
    result["lesson_scores"] = _lesson_scores(summary, controls_passed=controls_passed)
    return result




def _lessons(root_slice: Mapping[str, Any]) -> list[dict[str, Any]]:
    scores = root_slice["lesson_scores"]
    summary = root_slice["summary"]
    return [
        {
            "lesson_id": lesson_id,
            "statement": statement,
            "development_score": float(scores[lesson_id]),
            "development_cost": 1.0,
            "development_evidence": {
                "root_actor": root_slice["actor"],
                "root_arm_count": summary["arm_count"],
                "mean_all_history_fractional_rmse_reduction": summary[
                    "mean_all_history_fractional_rmse_reduction"
                ],
                "mean_identity_advantage": summary["mean_identity_advantage"],
                "positive_arm_fraction": summary["positive_arm_fraction"],
                "controls_passed": root_slice["controls_passed"],
            },
        }
        for lesson_id, statement in LESSON_STATEMENTS.items()
    ]


def _aggregate_slices(slices: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    per_arm: dict[str, Mapping[str, Any]] = {}
    assigned_roots: list[str] = []
    for actor, result in slices.items():
        if result.get("actor") != actor:
            raise TemporalAuthorityError("hive slice actor identity differs from its assignment")
        assigned_roots.extend(str(root) for root in result["assigned_roots"])
        for arm_id, arm in result["per_arm"].items():
            if arm_id in per_arm:
                raise TemporalAuthorityError("hive slices overlap on a development arm")
            per_arm[str(arm_id)] = arm
    expected = list(CAMPAIGN.development_roots)
    if sorted(assigned_roots) != sorted(expected) or len(assigned_roots) != len(expected):
        raise TemporalAuthorityError("hive population does not cover the development arms exactly once")
    summary = _summarize_arms(per_arm)
    controls_passed = all(bool(result["controls_passed"]) for result in slices.values())
    return {
        "arm_count": len(per_arm),
        "actor_count": len(slices),
        "assigned_roots": assigned_roots,
        "summary": summary,
        "controls_passed": controls_passed,
        "lesson_scores": _lesson_scores(summary, controls_passed=controls_passed),
        "slice_digests": {
            actor: _digest(result)
            for actor, result in slices.items()
        },
    }


def run_hive_campaign(workspace: Path, organism_home: Path) -> dict[str, Any]:
    """Run all disjoint readings and turn the result into challenged Hive knowledge."""
    workspace = Path(workspace).resolve(strict=True)
    organism_home = Path(organism_home).resolve()
    organism = ResearchOrganism(organism_home, workspace=workspace)
    if not organism.manifest_path.is_file():
        raise TemporalAuthorityError(
            "temporal authority requires an initialized living research organism"
        )
    manifest = organism._load_manifest()
    member_ids = tuple(str(member_id) for member_id in manifest["member_ids"])
    if len(member_ids) < 2:
        raise TemporalAuthorityError(
            "temporal authority requires at least two independent Hive reviewers"
        )
    actors = ("root", *member_ids)
    roots = tuple(CAMPAIGN.development_roots)
    partitions = {
        actor: tuple(roots[index::len(actors)])
        for index, actor in enumerate(actors)
    }
    if any(not assigned for assigned in partitions.values()):
        raise TemporalAuthorityError("Hive population exceeds the available development arms")

    prior = _load_prior_finding(workspace)
    analysis_sources = _source_manifest(
        workspace,
        tuple(str(path) for path in manifest["source_paths"]),
    )
    slices: dict[str, dict[str, Any]] = {}
    with _activated():
        for actor in actors:
            print(f"[{actor}] measuring {len(partitions[actor])} disjoint trajectory arms", flush=True)
            slices[actor] = _scan_active_slice(
                workspace,
                actor=actor,
                roots=partitions[actor],
                prior=prior,
                analysis_sources=analysis_sources,
            )
    aggregate = _aggregate_slices(slices)
    root_slice = slices["root"]
    member_results = {
        member_id: slices[member_id]
        for member_id in member_ids
    }
    assimilation = organism.assimilate_experiment(
        experiment_id=EXPERIMENT_ID,
        laboratory_id=LABORATORY_ID,
        objective=(
            "determine whether identity-aligned lag and derivative-equivalent trajectory "
            "history has stable acceleration authority beyond the complete present snapshot"
        ),
        root_result=root_slice,
        lessons=_lessons(root_slice),
        member_results=member_results,
    )
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "scope": "one integrated disjoint-arm Hive campaign; no isolated experiment path",
        "organism_home": str(organism_home),
        "collective_hive_home": str(organism.collective_hive_home),
        "prior_finding": prior,
        "analysis_sources": analysis_sources,
        "partition": {actor: list(assigned) for actor, assigned in partitions.items()},
        "slices": slices,
        "aggregate": aggregate,
        "hive_assimilation": assimilation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--organism-home", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite integrated Hive receipt: {args.out}")
    result = run_hive_campaign(args.workspace, args.organism_home)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "schema": result["schema"],
        "experiment_id": result["experiment_id"],
        "aggregate": result["aggregate"],
        "hive_assimilation": result["hive_assimilation"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
