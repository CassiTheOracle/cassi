"""Field-owned morphology-aware successor to the receipt-bound V4 operator search.

This module activates the proven V4 search machinery with a larger, independently
hash-bound target-independent alphabet.  It never edits the V4 executor or receipt.
"""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any, Iterator, Mapping

import numpy as np

import cassi_field_operator_invention as typed
import cassi_full_observable_invention as legacy
from cassi_full_observable_invention import CampaignSpec, OperatorInventionError
from cassi_morphology_observables import MORPHOLOGY_ATOMS, morphology_atoms
from cassi_morphology_operator_language import (
    MUTATION_COMPANIONS,
    OPERATOR_ATOMS,
    enrich_snapshot_atoms,
)

SCHEMA = "cassifi.morphology-operator.v1"
VERIFICATION_SCHEMA = "cassifi.morphology-operator-verification.v1"
CAMPAIGN_KIND = "morphology-operator-v2-20260920"
PROTOCOL = "CassiCosmos/research/equation_discovery/morphology_operator_v2_protocol.md"
PREVIOUS_RECEIPT = "CassiFI/_diag/full-observable-operator-v4/receipt.json"
SOURCE_PATHS = (
    "CassiFI/cassi_morphology_operator_invention.py",
    "CassiFI/cassi_morphology_operator_language.py",
    "CassiFI/cassi_morphology_observables.py",
    "CassiFI/cassi_full_observable_invention.py",
    "CassiFI/cassi_field_operator_invention.py",
    "CassiFI/cassi_research_residency.py",
)
CAMPAIGN = CampaignSpec(
    kind=CAMPAIGN_KIND,
    preregistration=PROTOCOL,
    development_roots=tuple(root for root in legacy._DEVELOPMENT_ROOTS if not root.endswith("/GL3")),
    hidden_holdout=tuple(
        f"CassiCosmos/_diag/matter_formation/morphology_operator_v1_20260919/{name}"
        for name in ("MH3", "MH6", "MHC3", "MHL3")
    ),
)

# The regional field's target-independent observation capacity is 256 per
# resident session. Six seed pools, six mutation pools, and the final synthesis
# must fit below it, so V2 uses sixteen candidates in each local decision:
# ten dynamic baseline coordinates plus all six morphology coordinates.
SEED_ATOMS = (
    "one", "q", "speed", "radial_speed", "transverse_speed",
    "field_energy", "local_density", "enclosed_mass", "divergence", "shear",
    *MORPHOLOGY_ATOMS,
)
SELECTION_MUTATION_COMPANIONS = (
    "q", "field_energy", "morphology_compactness", "morphology_radial_spread",
)
if len(SEED_ATOMS) != 16 or len(SELECTION_MUTATION_COMPANIONS) != 4:
    raise RuntimeError("morphology selection-budget contract drifted")

def _selection_seed_scalars() -> list[dict[str, Any]]:
    return [typed._atom(name) for name in SEED_ATOMS]


def _selection_mutations(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [typed._canonical_program(parent)]
    rows.extend({"op": op, "arg": parent} for op in legacy.UNARY_OPS)
    rows.extend({"op": "multiply", "args": [parent, typed._atom(name)]} for name in SELECTION_MUTATION_COMPANIONS)
    rows.extend(
        {"op": "divide_one_plus_abs", "numerator": parent, "denominator": typed._atom(name)}
        for name in SELECTION_MUTATION_COMPANIONS
    )
    canonical = {legacy._digest(typed._canonical_program(row)): typed._canonical_program(row) for row in rows}
    result = [canonical[key] for key in sorted(canonical)]
    if not 2 <= len(result) <= 32:
        raise OperatorInventionError("morphology mutation family exceeds selection bound")
    return result


def _directions(count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(count, 3))
    return values / np.linalg.norm(values, axis=1, keepdims=True)


def _tangential(radial: np.ndarray) -> np.ndarray:
    axis = np.tile(np.array((0.0, 0.0, 1.0)), (len(radial), 1))
    velocity = np.cross(radial, axis)
    near_axis = np.linalg.norm(velocity, axis=1) < 1e-9
    velocity[near_axis] = np.cross(radial[near_axis], np.array((0.0, 1.0, 0.0)))
    return velocity / np.linalg.norm(velocity, axis=1, keepdims=True)


def _morphology_controls(base_controls: Mapping[str, Any]) -> dict[str, Any]:
    """Add can-fail geometry witnesses to the inherited scalar-language controls."""
    count = 256
    radial = _directions(count, 71)
    shell_position = radial * (3.0 + 0.01 * np.sin(np.arange(count)))[:, None]
    shell = morphology_atoms(shell_position, _tangential(radial), np.ones(count))
    rng = np.random.default_rng(73)
    cloud_position = rng.normal(size=(count, 3))
    cloud = morphology_atoms(cloud_position, rng.normal(size=(count, 3)), np.ones(count))
    nested = morphology_atoms(
        _directions(count, 79) * np.where(np.arange(count) % 2 == 0, 1.0, 4.0)[:, None],
        _tangential(_directions(count, 79)),
        np.ones(count),
    )
    angle = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    disc_position = np.column_stack((2.0 * np.cos(angle), 2.0 * np.sin(angle), 0.002 * np.sin(3.0 * angle)))
    disc = morphology_atoms(disc_position, np.column_stack((-np.sin(angle), np.cos(angle), np.zeros(count))), np.ones(count))
    normal = shell_position / np.linalg.norm(shell_position, axis=1, keepdims=True)
    coherent = morphology_atoms(shell_position, normal, np.ones(count))
    counterflow = morphology_atoms(shell_position, np.where((np.arange(count) % 2)[:, None] == 0, -normal, normal), np.ones(count))
    fired = (
        float(np.mean(shell["morphology_shell_tangentiality"])) > float(np.mean(cloud["morphology_shell_tangentiality"])) + 0.15
        and float(np.mean(nested["morphology_radial_spread"])) > float(np.mean(shell["morphology_radial_spread"])) + 0.25
        and float(np.mean(disc["morphology_anisotropy"])) > float(np.mean(cloud["morphology_anisotropy"])) + 0.45
        and float(np.mean(disc["morphology_planarity"])) > float(np.mean(cloud["morphology_planarity"])) + 0.45
        and float(np.mean(counterflow["morphology_counterflow"])) > float(np.mean(coherent["morphology_counterflow"])) + 0.35
    )
    controls = dict(base_controls)
    controls["alphabet"] = {
        "status": "PASS" if len(OPERATOR_ATOMS) == 37 and len(legacy.FRAMES) == 6 else "FAIL",
        "atom_count": len(OPERATOR_ATOMS),
        "frame_count": len(legacy.FRAMES),
    }
    controls["morphology-contrast"] = {
        "status": "PASS" if fired else "FAIL",
        "shell_tangentiality": float(np.mean(shell["morphology_shell_tangentiality"])),
        "cloud_tangentiality": float(np.mean(cloud["morphology_shell_tangentiality"])),
        "nested_spread": float(np.mean(nested["morphology_radial_spread"])),
        "shell_spread": float(np.mean(shell["morphology_radial_spread"])),
        "disc_anisotropy": float(np.mean(disc["morphology_anisotropy"])),
        "cloud_anisotropy": float(np.mean(cloud["morphology_anisotropy"])),
        "counterflow": float(np.mean(counterflow["morphology_counterflow"])),
        "coherent_flow": float(np.mean(coherent["morphology_counterflow"])),
    }
    if any(control["status"] != "PASS" for control in controls.values()):
        raise OperatorInventionError("morphology calibration control failed")
    return controls


@contextlib.contextmanager
def _activated() -> Iterator[None]:
    """Temporarily configure the V4 mechanics for this distinct, bound language."""
    saved = {
        "atoms": legacy.ATOMS,
        "companions": legacy.MUTATION_COMPANIONS,
        "typed_atoms": typed.ATOMS,
        "schema": legacy.SCHEMA,
        "verification_schema": legacy.VERIFICATION_SCHEMA,
        "previous_receipt": legacy._PREVIOUS_RECEIPT,
        "module_file": legacy.__file__,
        "snapshot": legacy._snapshot_features,
        "expected_sources": legacy._expected_source_paths,
        "seed_scalars": legacy._seed_scalars,
        "mutations": legacy._mutations,
        "calibration": legacy.calibration_controls,
    }
    original_snapshot = legacy._snapshot_features
    original_calibration = legacy.calibration_controls
    original_expected_sources = legacy._expected_source_paths

    def snapshot(*args: Any, **kwargs: Any) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        legacy.ATOMS = saved["atoms"]
        try:
            atoms, frames = original_snapshot(*args, **kwargs)
        finally:
            legacy.ATOMS = OPERATOR_ATOMS
        return enrich_snapshot_atoms(atoms, args[0], args[1], args[2], neighbor_count=legacy.NEIGHBOR_COUNT, minimum_radius=legacy.MINIMUM_RADIUS), frames

    def calibration() -> dict[str, Any]:
        legacy.ATOMS = saved["atoms"]
        typed.ATOMS = saved["typed_atoms"]
        try:
            base = original_calibration()
        finally:
            legacy.ATOMS = OPERATOR_ATOMS
            typed.ATOMS = OPERATOR_ATOMS
        return _morphology_controls(base)

    def expected_sources(campaign: CampaignSpec) -> list[str]:
        return sorted((*original_expected_sources(campaign), *SOURCE_PATHS))

    try:
        legacy.ATOMS = OPERATOR_ATOMS
        legacy.MUTATION_COMPANIONS = MUTATION_COMPANIONS
        typed.ATOMS = OPERATOR_ATOMS
        legacy.SCHEMA = SCHEMA
        legacy.VERIFICATION_SCHEMA = VERIFICATION_SCHEMA
        legacy._PREVIOUS_RECEIPT = PREVIOUS_RECEIPT
        legacy.__file__ = __file__
        legacy._snapshot_features = snapshot
        legacy._expected_source_paths = expected_sources
        legacy._seed_scalars = _selection_seed_scalars
        legacy._mutations = _selection_mutations
        legacy.calibration_controls = calibration
        legacy._CAMPAIGNS[CAMPAIGN_KIND] = CAMPAIGN
        legacy._load_bundle.cache_clear()
        yield
    finally:
        legacy._load_bundle.cache_clear()
        legacy._CAMPAIGNS.pop(CAMPAIGN_KIND, None)
        legacy.ATOMS = saved["atoms"]
        legacy.MUTATION_COMPANIONS = saved["companions"]
        typed.ATOMS = saved["typed_atoms"]
        legacy.SCHEMA = saved["schema"]
        legacy.VERIFICATION_SCHEMA = saved["verification_schema"]
        legacy._PREVIOUS_RECEIPT = saved["previous_receipt"]
        legacy.__file__ = saved["module_file"]
        legacy._snapshot_features = saved["snapshot"]
        legacy._expected_source_paths = saved["expected_sources"]
        legacy._seed_scalars = saved["seed_scalars"]
        legacy._mutations = saved["mutations"]
        legacy.calibration_controls = saved["calibration"]


def preflight_morphology_operator(workspace: Path) -> dict[str, Any]:
    """Run no-field, no-holdout reachability checks before generating fresh worlds."""
    workspace = Path(workspace).resolve(strict=True)
    with _activated():
        controls = legacy.calibration_controls()
        fit_arms, validation_arms = legacy._load_development(workspace, CAMPAIGN)
        for arm in (*fit_arms, *validation_arms):
            energy = float(np.einsum("ij,ij->", arm.target, arm.target))
            if not np.isfinite(energy) or energy <= 0.0:
                raise OperatorInventionError(f"morphology development arm has invalid target energy: {arm.arm_id}")
        mutation_count = len(legacy._mutations(legacy._seed_scalars()[0]))
        if len(legacy._seed_scalars()) != 16 or not 2 <= mutation_count <= 16:
            raise OperatorInventionError("morphology selection surface is not within the resident bound")
        return {
            "schema": SCHEMA,
            "status": "PASS",
            "atom_count": len(OPERATOR_ATOMS),
            "frame_count": len(legacy.FRAMES),
            "fit_arm_count": len(fit_arms),
            "validation_arm_count": len(validation_arms),
            "controls": controls,
        }


def run_morphology_operator_invention(organism: Any, *, workspace: Path) -> dict[str, Any]:
    with _activated():
        return legacy.run_full_observable_invention(organism, workspace=workspace, campaign_kind=CAMPAIGN_KIND)


def verify_morphology_operator_receipt(receipt: Mapping[str, Any], *, check_mutation_controls: bool = True) -> dict[str, Any]:
    with _activated():
        return legacy.verify_full_observable_receipt(receipt, check_mutation_controls=check_mutation_controls)


__all__ = [
    "CAMPAIGN", "CAMPAIGN_KIND", "OPERATOR_ATOMS", "SCHEMA", "VERIFICATION_SCHEMA",
    "preflight_morphology_operator", "run_morphology_operator_invention", "verify_morphology_operator_receipt",
]
