"""Development-only conditional authority reading for morphology observables.

This is a diagnostic, not another operator invention run.  It asks whether each
morphology channel removes acceleration residual left after the V2 dynamic base
coordinates, using chronological train/validation segments only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

import cassi_full_observable_invention as legacy
from cassi_morphology_observables import MORPHOLOGY_ATOMS
from cassi_morphology_operator_invention import CAMPAIGN, SEED_ATOMS, _activated

BASE_ATOMS = tuple(atom for atom in SEED_ATOMS if atom not in MORPHOLOGY_ATOMS)
RIDGE = 1e-10


def _matrix(bundle: legacy.FeatureBundle, atoms: Iterable[str]) -> np.ndarray:
    columns: list[np.ndarray] = []
    for atom in atoms:
        scalar = np.asarray(bundle.atoms[atom], dtype=np.float64)
        rms = float(np.sqrt(np.mean(scalar * scalar)))
        if not np.isfinite(rms) or rms <= 1e-12:
            scalar = np.zeros_like(scalar)
        else:
            scalar = scalar / rms
        for frame in legacy.FRAMES:
            columns.append(np.asarray(bundle.frames[frame], dtype=np.float64) * scalar[:, None])
    return np.concatenate(columns, axis=1)


def _solve(design: np.ndarray, target: np.ndarray) -> np.ndarray:
    gram = design.T @ design
    ridge = RIDGE * max(1.0, float(np.trace(gram)) / max(1, gram.shape[0]))
    return np.linalg.solve(gram + ridge * np.eye(gram.shape[0]), design.T @ target)


def _nrmse(prediction: np.ndarray, target: np.ndarray) -> float:
    target_rms = float(np.sqrt(np.mean(target * target)))
    if not np.isfinite(target_rms) or target_rms <= 1e-12:
        raise ValueError("authority target has zero RMS")
    return float(np.sqrt(np.mean((prediction - target) ** 2)) / target_rms)


def conditional_reading(
    train_base: np.ndarray,
    validation_base: np.ndarray,
    train_morphology: np.ndarray,
    validation_morphology: np.ndarray,
    train_target: np.ndarray,
    validation_target: np.ndarray,
) -> dict[str, float]:
    """Measure held-out residual authority for one morphology design block."""
    base_coefficients = _solve(train_base, train_target)
    base_prediction = validation_base @ base_coefficients
    enriched_train = np.concatenate((train_base, train_morphology), axis=1)
    enriched_validation = np.concatenate((validation_base, validation_morphology), axis=1)
    enriched_prediction = enriched_validation @ _solve(enriched_train, train_target)
    baseline = _nrmse(base_prediction, validation_target)
    enriched = _nrmse(enriched_prediction, validation_target)
    return {
        "baseline_nrmse": baseline,
        "enriched_nrmse": enriched,
        "fractional_rmse_reduction": float(1.0 - enriched / baseline),
    }


def _conditional_spectrum(base: np.ndarray, morphology: np.ndarray) -> dict[str, Any]:
    residual = morphology - base @ _solve(base, morphology)
    singular = np.linalg.svd(residual, compute_uv=False)
    tolerance = float(max(residual.shape) * np.finfo(np.float64).eps * (singular[0] if len(singular) else 0.0))
    rank = int(np.count_nonzero(singular > tolerance))
    return {
        "shape": [int(value) for value in residual.shape],
        "rank": rank,
        "tolerance": tolerance,
        "singular_values": [float(value) for value in singular],
        "sigma_min": float(singular[-1]) if len(singular) else 0.0,
    }


def _pair_separation(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) + np.linalg.norm(right))
    return 0.0 if denominator <= 1e-12 else float(np.linalg.norm(left - right) / denominator)


def scan_morphology_authority(workspace: Path) -> dict[str, Any]:
    """Read morphology's conditional predictive authority on disclosed V2 development only."""
    workspace = Path(workspace).resolve(strict=True)
    with _activated():
        fit, validation = legacy._load_development(workspace, CAMPAIGN)
        by_id = {bundle.arm_id: bundle for bundle in validation}
        if set(bundle.arm_id for bundle in fit) != set(by_id):
            raise ValueError("chronological development arms do not pair")

        per_arm: dict[str, Any] = {}
        aggregate_train_base: list[np.ndarray] = []
        aggregate_train_morphology: list[np.ndarray] = []
        per_atom_reductions: dict[str, list[float]] = {atom: [] for atom in MORPHOLOGY_ATOMS}
        combined_reductions: list[float] = []
        injected_reductions: list[float] = []

        for train_bundle in fit:
            validation_bundle = by_id[train_bundle.arm_id]
            train_base = _matrix(train_bundle, BASE_ATOMS)
            validation_base = _matrix(validation_bundle, BASE_ATOMS)
            train_morphology = _matrix(train_bundle, MORPHOLOGY_ATOMS)
            validation_morphology = _matrix(validation_bundle, MORPHOLOGY_ATOMS)
            combined = conditional_reading(
                train_base, validation_base, train_morphology, validation_morphology,
                train_bundle.target, validation_bundle.target,
            )
            atoms: dict[str, Any] = {}
            for atom_index, atom in enumerate(MORPHOLOGY_ATOMS):
                start = atom_index * 3 * len(legacy.FRAMES)
                stop = start + 3 * len(legacy.FRAMES)
                reading = conditional_reading(
                    train_base, validation_base, train_morphology[:, start:stop], validation_morphology[:, start:stop],
                    train_bundle.target, validation_bundle.target,
                )
                atoms[atom] = reading
                per_atom_reductions[atom].append(reading["fractional_rmse_reduction"])

            # Firing control: first remove every base-channel projection from a
            # real compactness design block, then inject that held-out residual
            # direction into actual acceleration arrays. The enriched model can
            # recover it; the base-only model cannot by construction.
            control_train = train_morphology[:, : 3 * len(legacy.FRAMES)]
            control_validation = validation_morphology[:, : 3 * len(legacy.FRAMES)]
            control_projection = _solve(train_base, control_train)
            residual_train = control_train - train_base @ control_projection
            residual_validation = control_validation - validation_base @ control_projection
            control_rms = float(np.sqrt(np.mean(residual_train[:, :3] * residual_train[:, :3])))
            target_rms = float(np.sqrt(np.mean(train_bundle.target * train_bundle.target)))
            gain = 0.5 * target_rms / max(control_rms, 1e-12)
            injected = conditional_reading(
                train_base, validation_base, control_train, control_validation,
                train_bundle.target + gain * residual_train[:, :3],
                validation_bundle.target + gain * residual_validation[:, :3],
            )
            injected_reductions.append(injected["fractional_rmse_reduction"])
            combined_reductions.append(combined["fractional_rmse_reduction"])
            per_arm[train_bundle.arm_id] = {
                "combined": combined,
                "atoms": atoms,
                "injected_compactness_control": injected,
            }
            aggregate_train_base.append(train_base)
            aggregate_train_morphology.append(train_morphology)

        stacked_base = np.concatenate(aggregate_train_base, axis=0)
        stacked_morphology = np.concatenate(aggregate_train_morphology, axis=0)
        pair_separation = {
            f"{left}:{right}": _pair_separation(
                stacked_morphology[:, left_index * 3 * len(legacy.FRAMES):(left_index + 1) * 3 * len(legacy.FRAMES)],
                stacked_morphology[:, right_index * 3 * len(legacy.FRAMES):(right_index + 1) * 3 * len(legacy.FRAMES)],
            )
            for left_index, left in enumerate(MORPHOLOGY_ATOMS)
            for right_index, right in enumerate(MORPHOLOGY_ATOMS[left_index + 1:], start=left_index + 1)
        }
        duplicate = np.concatenate((stacked_morphology, stacked_morphology[:, :3 * len(legacy.FRAMES)]), axis=1)
        spectrum = _conditional_spectrum(stacked_base, stacked_morphology)
        duplicate_spectrum = _conditional_spectrum(stacked_base, duplicate)
        firing = float(np.mean(injected_reductions)) > 0.25
        duplicate_ok = duplicate_spectrum["rank"] == spectrum["rank"]
        if not firing or not duplicate_ok:
            raise ValueError("morphology authority controls did not fire")
        return {
            "schema": "cassifi.morphology-residual-authority.v1",
            "scope": "development-only chronological residual reading; not a holdout verdict",
            "base_atoms": list(BASE_ATOMS),
            "morphology_atoms": list(MORPHOLOGY_ATOMS),
            "arm_count": len(per_arm),
            "per_arm": per_arm,
            "mean_combined_fractional_rmse_reduction": float(np.mean(combined_reductions)),
            "mean_fractional_rmse_reduction_by_atom": {
                atom: float(np.mean(values)) for atom, values in per_atom_reductions.items()
            },
            "conditional_morphology_spectrum": spectrum,
            "pair_separation": pair_separation,
            "duplicate_identity_control": {
                "status": "PASS" if duplicate_ok else "FAIL",
                "rank": duplicate_spectrum["rank"],
                "reference_rank": spectrum["rank"],
            },
            "injected_compactness_control": {
                "status": "PASS" if firing else "FAIL",
                "mean_fractional_rmse_reduction": float(np.mean(injected_reductions)),
            },
        }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite authority reading: {args.out}")
    result = scan_morphology_authority(args.workspace)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
